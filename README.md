OCA-Port Scanner
================

TODO


About keeping up-to-date the list of OCA repositories
-----------------------------------------------------

The way the list of OCA repositories has been done initially is a bit clunky.

First, list all OCA repositories thanks to the GitHub API and `jq` utility:

```sh
$ curl 'https://api.github.com/orgs/OCA/repos?sort=full_name&per_page=100&page=1' | jq '.[].full_name' > repos.lst
$ curl 'https://api.github.com/orgs/OCA/repos?sort=full_name&per_page=100&page=2' | jq '.[].full_name' >> repos.lst
$ curl 'https://api.github.com/orgs/OCA/repos?sort=full_name&per_page=100&page=3' | jq '.[].full_name' >> repos.lst
```

To detect new repositories, re-run the same commands later on but in another
file, and compare it to the former:

```sh
$ diff -u old_repos.lst new_repos.lst
```

Check if the new repositories aim to host Odoo modules, and add them to the list
of repositories in the configuration file before restarting the scanner.
