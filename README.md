# saltyHangout
A Hangouts-Chat Bot for SaltStack

## Why?
Because some people in companies prefer to use a GUI to manage their machines.\
It's of course not a typically GUI but it's much easier for people to interact with SaltStack.

## Installation
Clone or copy the engine file to your SaltStack environment and set the SaltStack configuration as shown below.

## Sample SaltStack Engine-Conf
/etc/salt/master.d/engines.conf or /etc/salt/master or wherever your configuration file is located.
```yaml
engines_dirs:
  - /srv/engines

engines:
  - bot_hangouts_chat:
      hsalt:
        credentials: /etc/salt/master.d/<credential file>.json
        project: testproject-123456
        subscription_name: testproject
        commands:
          /lookup_jid:
            module: jobs.lookup_jid
            backend: __runners__
            arguments:
              - jid
            description: Prints the available data to the given jid.
          /list_jobs:
            module: jobs.list_jobs
            backend: __runners__
            description: Lists all available jobs.
          /ping:
            module: test.ping
            backend: salt
            description: Pings the given Minion
            arguments:
              - pc_name
          /state_apply:
            module: state.apply
            arguments:
              - pc_name
            optional_arguments:
              - <state file>
            backend: salt
            description: Run Highstate or a specific sls on the given Minion
```

## Limitation
I had to cut off some output as Google accepts only 4096 characters as input.\
At the moment I cut off all except the last 10 entries in the dict.\
That's something I've to think about again, but for the moment it works.
