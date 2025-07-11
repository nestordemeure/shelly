## LMOD: Environment Module System**

LMOD is used to manage the user's shell environment, allowing you to easily load and unload software packages, compilers, and libraries without conflicts. The primary command is module, often aliased to ml.

| Sub-command | Alias | Description & Example |
| :---- | :---- | :---- |
| avail | av | **Lists all available modules.**\<br/\>module avail (list all)\<br/\>module avail gcc (list modules matching "gcc") |
| list |  | **Lists all currently loaded modules.**\<br/\>module list |
| load |  | **Loads one or more modules into the environment.**\<br/\>module load python/3.9.12 gcc/11.2.0 |
| unload |  | **Unloads one or more modules.**\<br/\>module unload python |
| swap | sw | **Unloads the first module and loads the second.**\<br/\>module swap gcc/11.2.0 gcc/12.1.0 |
| purge |  | **Unloads all currently loaded modules.**\<br/\>module purge |
| spider |  | **Searches the entire module hierarchy.** Useful for finding modules that aren't immediately available.\<br/\>module spider cuda |
| whatis |  | **Gives a brief description of a module.**\<br/\>module whatis cray-mpich |
| help |  | **Displays the help text from within a module file.**\<br/\>module help anaconda3 |
| save \<name\> |  | **Saves the current list of loaded modules to a named collection.**\<br/\>module save my\_project\_env |
| restore \<name\> |  | **Restores a previously saved collection of modules.**\<br/\>module restore my\_project\_env |
