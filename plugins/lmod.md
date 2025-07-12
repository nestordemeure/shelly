# LMOD: Environment Module System (v8.7.37)

LMOD is used to manage the user's shell environment, allowing you to easily load and unload software packages, compilers, and libraries.

## Usage

```bash
module [options] sub-command [args ...]
```

## Options

| Option                                | Description                                                                              |
| ------------------------------------- | ---------------------------------------------------------------------------------------- |
| `-h`, `-?`, `-H`, `--help`            | This help message                                                                        |
| `-s availStyle`, `--style=availStyle` | Site controlled avail style: system (default: system)                                    |
| `--regression_testing`                | Lmod regression testing                                                                  |
| `-b`, `--brief`                       | Brief listing with only user specified modules                                           |
| `-D`                                  | Program tracing written to stderr                                                        |
| `--debug=dbglvl`                      | Program tracing written to stderr (where dbglvl is a number 1,2,3)                       |
| `--pin_versions=pinVersions`          | When doing a restore use specified version, do not follow defaults                       |
| `-d`, `--default`                     | List default modules only when used with `avail`                                         |
| `-q`, `--quiet`                       | Do not print out warnings                                                                |
| `--expert`                            | Expert mode                                                                              |
| `-t`, `--terse`                       | Write out in machine readable format for commands: `list`, `avail`, `spider`, `savelist` |
| `--initial_load`                      | Loading Lmod for first time in a user shell                                              |
| `--latest`                            | Load latest (ignore default)                                                             |
| `-I`, `--ignore_cache`                | Treat the cache file(s) as out-of-date                                                   |
| `--novice`                            | Turn off expert and quiet flag                                                           |
| `--raw`                               | Print modulefile in raw output when used with `show`                                     |
| `-w twidth`, `--width=twidth`         | Use this as max terminal width                                                           |
| `-v`, `--version`                     | Print version info and quit                                                              |
| `-r`, `--regexp`                      | Use regular expression match                                                             |
| `--gitversion`                        | Dump git version in a machine readable way and quit                                      |
| `--dumpversion`                       | Dump version in a machine readable way and quit                                          |
| `--check_syntax`, `--checkSyntax`     | Check module command syntax: do not load                                                 |
| `--config`                            | Report Lmod Configuration                                                                |
| `--miniConfig`                        | Report Lmod Configuration differences                                                    |
| `--config_json`                       | Report Lmod Configuration in JSON format                                                 |
| `--mt`                                | Report Module Table State                                                                |
| `--timer`                             | Report run times                                                                         |
| `-f`, `--force`                       | Force removal of a sticky module or save an empty collection                             |
| `--redirect`                          | Send output of `list`, `avail`, `spider` to stdout (not stderr)                          |
| `--no_redirect`                       | Force output of `list`, `avail`, and `spider` to stderr                                  |
| `--show_hidden`                       | `avail` and `spider` will report hidden modules                                          |
| `--spider_timeout=timeout`            | Set a timeout for `spider`                                                               |
| `-T`, `--trace`                       | Enable tracing                                                                           |
| `--nx`, `--no_extensions`             | Disable extensions                                                                       |
| `--loc`, `--location`                 | Just print file location when using `show`                                               |
| `--terse_show_extensions`             | Enable terse output for showing extensions                                               |

## Sub-commands

### Help

| Command             | Description                       |
| ------------------- | --------------------------------- |
| `help`              | Prints this message               |
| `help module [...]` | Print help message from module(s) |

### Loading / Unloading

| Command                            | Description                                    |
| ---------------------------------- | ---------------------------------------------- |
| `load`, `add module [...]`         | Load module(s)                                 |
| `try-load`, `try-add module [...]` | Add module(s), do not complain if not found    |
| `del`, `unload module [...]`       | Remove module(s), do not complain if not found |
| `swap`, `sw`, `switch m1 m2`       | Unload `m1` and load `m2`                      |
| `purge`                            | Unload all modules                             |
| `refresh`                          | Reload aliases from current list of modules    |
| `update`                           | Reload all currently loaded modules            |

### Listing / Searching

| Command                 | Description                                                    |
| ----------------------- | -------------------------------------------------------------- |
| `list`                  | List loaded modules                                            |
| `list s1 s2 ...`        | List loaded modules that match the pattern                     |
| `avail`, `av`           | List available modules                                         |
| `avail string`          | List available modules that contain `"string"`                 |
| `category`, `cat`       | List all categories                                            |
| `category s1 s2 ...`    | List all categories matching pattern and display their modules |
| `overview`, `ov`        | List available modules by short names with number of versions  |
| `overview string`       | Same as above, but filter by `"string"`                        |
| `spider`                | List all possible modules                                      |
| `spider module`         | List all possible versions of that module                      |
| `spider string`         | List all modules containing `"string"`                         |
| `spider name/version`   | Detailed information about a specific version                  |
| `whatis module`         | Print whatis information about a module                        |
| `keyword`, `key string` | Search all names and whatis for those containing `"string"`    |

### Searching with Lmod

All searching (`spider`, `list`, `avail`, `keyword`) supports regular expressions:

```bash
-r spider '^p'         # Finds modules starting with "p" or "P"
-r spider mpi          # Finds modules with "mpi" in their name
-r spider 'mpi$'       # Finds modules ending with "mpi"
```

### Collections of Modules

| Command                | Description                                               |
| ---------------------- | --------------------------------------------------------- |
| `save`, `s`            | Save current modules to user-defined "default" collection |
| `save name`            | Save current modules to `"name"` collection               |
| `reset`                | Equivalent to `restore system`                            |
| `restore`, `r`         | Restore modules from user's "default" or system default   |
| `restore name`         | Restore modules from `"name"` collection                  |
| `restore system`       | Restore module state to system defaults                   |
| `savelist`             | List saved collections                                    |
| `describe`, `mcc name` | Describe the contents of a module collection              |
| `disable name`         | Disable (remove) a collection                             |

### Miscellaneous

| Command                | Description                                  |
| ---------------------- | -------------------------------------------- |
| `is-loaded modulefile` | Return true if module is loaded              |
| `is-avail modulefile`  | Return true if module can be loaded          |
| `show modulefile`      | Show commands in the module file             |
| `use [-a] path`        | Prepend or append `path` to `MODULEPATH`     |
| `unuse path`           | Remove `path` from `MODULEPATH`              |
| `tablelist`            | Output list of active modules as a Lua table |
