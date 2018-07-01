#!/usr/bin/env python
from google.cloud import pubsub  # https://cloud.google.com/pubsub/docs/reference/libraries
import os
import time
import json
# noinspection PyUnresolvedReferences
import salt.utils.event
import logging
from oauth2client.service_account import ServiceAccountCredentials
from httplib2 import Http
# noinspection PyUnresolvedReferences
from apiclient.discovery import build
import yaml
# noinspection PyUnresolvedReferences
from salt.client import LocalClient
import re
from collections import OrderedDict

log = logging.getLogger(__name__)

__author__ = "Christian Schirge"
__license__ = "MIT"
__version__ = "0.0.1"
__maintainer__ = "Christian Schirge"
__email__ = "christian.schirge@gmail.com"
__status__ = "Testing"

local = LocalClient()


class HangoutsChatBot:
    def __init__(
            self,
            credentials=None,
            project=None,
            subscription_name=None,
            tag='engine/bot_hangouts_chat',
            commands=None):
        """

        :param credentials:
        :param project:
        :param subscription_name:
        :param tag:
        :param commands:
        """
        self.credentials = credentials
        self.project = project
        self.subscription_name = subscription_name
        self.tag = tag
        self.commands = commands
        self.message_dict = {}
        self.hc_args = ''
        self.answer = None
        self.scopes = ['https://www.googleapis.com/auth/chat.bot']
        self.thread = None
        self.fire_master = None
        # noinspection PyUnresolvedReferences
        self.backends = {'salt': local, '__salt__': __salt__, '__runners__': __runners__}
        self.re_true = re.compile('^true$', re.IGNORECASE)
        self.re_false = re.compile('^false$', re.IGNORECASE)
        self._create_fire()
        self._set_env()

    def start(self):
        """
        Receives messages from a pull subscription.
        """
        subscriber = pubsub.SubscriberClient()
        subscription_path = subscriber.subscription_path(
            self.project, self.subscription_name)

        def _callback(message):
            self.message_dict = json.loads(message.data)
            self._parse_args()
            message.ack()

            if self.hc_args[0] == u'/help':
                self._help()
            elif self.hc_args[0] in self.commands.keys():
                self._execute()
                self._fire()
            else:
                self.answer = 'If you need an overview of commands just send "/help" to me'
            self._to_chat()

        subscriber.subscribe(subscription_path, callback=_callback)

    def _arg_parse(self):
        """

        :return:
        """
        _str_args = self.hc_args[1:]
        self.args = []
        self.kwargs = {}

        for i in _str_args:
            if i.count('=') == 1:
                key, value = i.split('=', 1)
            else:
                key, value = None, i
            try:
                value = json.loads(value)
            except ValueError as _:
                pass
            if key:
                self.kwargs[key] = self._value_bool(value)
            else:
                self.args.append(i)

    def _create_fire(self):
        """

        :return:
        """
        # noinspection PyUnresolvedReferences
        if __opts__.get('__role') == 'master':
            # noinspection PyUnresolvedReferences
            self.fire_master = salt.utils.event.get_master_event(__opts__, __opts__['sock_dir']).fire_event

    def _execute(self):
        """

        :return:
        """
        self.values = self.commands.get(self.hc_args[0])
        self._arg_parse()

        if len(self.args) < len(self.values.get('arguments', [])):
            self.answer = 'No arguments'
            return

        if self.values.get('backend') == 'salt':
            self.answer = self.backends['salt'].cmd(
                self.args.pop(0),
                self.values.get('module'),
                arg=self.args,
                kwarg=self.kwargs
            )
        else:
            try:
                _run = self.backends[self.values.get('backend')]
            except (AttributeError, KeyError) as error:
                _run = False
                log.error('ERROR in backend - Name: {} - Error-Message: {}'.format(__name__, error))

            if _run:
                self.answer = _run[self.values.get('module')](*self.args, **self.kwargs)
            else:
                self.answer = 'Backend System couldn\'t be launched, please contact the admin!'

    def _fire(self, tag_spart=None, msg=None):
        """

        :param tag_spart:
        :param msg:
        :return:
        """
        tag = '{}/{}'.format(
            self.tag,
            tag_spart if tag_spart else self.message_dict.get('message', {}).get(
                'argumentText',
                'message'
            ).encode('utf-8')
        )
        if self.fire_master:
            self.fire_master(
                msg if msg else self.message_dict,
                tag
            )
        else:
            # noinspection PyUnresolvedReferences
            __salt__['event.send'](
                tag,
                msg if msg else self.message_dict
            )

    def _help(self):
        """

        :return:
        """
        self.answer = {}
        for key, value in self.commands.items():
            key_list = ['*{}*'.format(key)]
            arguments = ' '.join(value.get('arguments', []))
            if value.get('optional_arguments'):
                arguments = '{} {}'.format(arguments, ' '.join(value.get('optional_arguments')))
            if arguments:
                key_list.append(arguments)
            self.answer[' '.join(key_list)] = {'description': value.get('description')}

    def _parse_args(self):
        """

        :return:
        """
        self.hc_args = self.message_dict.get('message', {}).get('argumentText', 'message')
        self.hc_args = self.hc_args.split(' ')
        self.hc_args = filter(None, self.hc_args)

    def _set_env(self):
        """

        :return:
        """
        if self.credentials:
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = self.credentials
            return True
        return False

    def _to_chat(self):
        """

        :return:
        """
        thread_name = self.message_dict.get('message', {}).get('thread', {}).get('name', None)

        if hasattr(self.answer, 'get'):
            ordered = OrderedDict(
                sorted(self.answer.items()),
                key=lambda answer: answer[0]
            )
            while len(ordered) >= 11:
                ordered.popitem(last=False)
            ordered.popitem()
            self.answer = dict(ordered)

        body_dict = {
            'text': yaml.dump(self.answer, default_flow_style=False),
            'thread': {'name': thread_name}
        }
        credentials = ServiceAccountCredentials.from_json_keyfile_name(self.credentials, self.scopes)
        http_auth = credentials.authorize(Http())
        chat = build('chat', 'v1', http=http_auth)
        chat.spaces().messages().create(
            parent=self.message_dict.get('space').get('name'),
            body=body_dict).execute()

    def _value_bool(self, value):
        """

        :param value:
        :return:
        """
        if self.re_true.match(value):
            return True
        if self.re_false.match(value):
            return False
        return value


def start(**bots_dict):
    """

    :param bots_dict:
    :return:
    """
    boto_dict = {}
    for bot_key, bot_value in bots_dict.items():
        credentials = bot_value.get('credentials')
        project = bot_value.get('project')
        subscription_name = bot_value.get('subscription_name')
        tag = bot_value.get('tag', 'engine/bot_hangouts_chat')
        commands = bot_value.get('commands')
        boto_dict[bot_key] = HangoutsChatBot(
            credentials,
            project,
            subscription_name,
            tag,
            commands
        )
        boto_dict[bot_key].start()
    # SubscriberClient is non-blocking, so a while loop is included to make sure it is not going to close
    while True:
        time.sleep(60)
