# SLURM: Simple Linux Utility for Resource Management

SLURM is the queueing system used to manage and schedule jobs on Perlmutter. It provides a suite of commands to submit, monitor, and control computational work.

### Job Submission Commands

These commands are used to request resource allocations and run jobs.

#### `sbatch`

Submits a batch script to the SLURM queue for later execution.

**Synopsis**
`sbatch [OPTIONS]... [SCRIPT]`

**How it Works**
`sbatch` submits a script that typically begins with `#SBATCH` directives. These directives specify job options directly within the script. The command exits immediately after the job is successfully queued, providing a job ID. The job may wait in the queue before resources are allocated and it begins execution.

**Key Options**

* **Job Naming and Output:**
  * `-J, --job-name=<name>`: Specify a name for the job.
  * `-o, --output=<file>`: Path for standard output. By default, this is `slurm-%j.out`.
  * `-e, --error=<file>`: Path for standard error.
* **Resource Requests:**
  * `-N, --nodes=<count>`: Request a specific number of nodes.
  * `-n, --ntasks=<count>`: Request a specific number of tasks.
  * `-c, --cpus-per-task=<count>`: Request a number of CPUs for each task.
  * `--mem=<size>`: Specify memory required per node (e.g., `4G`, `100M`).
  * `--mem-per-cpu=<size>`: Specify memory required per CPU.
  * `-t, --time=<time>`: Set a time limit for the job (e.g., `1-12:30:00`, `30:00`).
  * `-p, --partition=<name>`: Request a specific partition [queue](cite: 610).
  * `-G, --gpus=<[type:]count>`: Request a total number of GPUs.
  * `--gpus-per-node=<[type:]count>`: Request a number of GPUs on each node.
* **Job Dependencies and Control:**
  * `-d, --dependency=<type:jobid>`: Defer job start until another job meets a condition. Common types are `afterok` (dependent job succeeded) and `afterany` [dependent job terminated](cite: 191, 196).
  * `--hold`: Submit the job in a held state.
  * `-a, --array=<indexes>`: Submit a job array, creating multiple jobs from a single script. Examples: `--array=1-10` or `--array=1,5,10`. A "slot limit" can be added with a `%` (e.g., `0-15%4`) to run a maximum of 4 tasks at once.
* **Email Notifications:**
  * `--mail-user=<address>`: Email address for notifications.
  * `--mail-type=<type>`: Specify event for notification (e.g., `BEGIN`, `END`, `FAIL`, `ALL`).

#### `srun`

Runs a parallel job or a step within an existing job allocation. `srun` can either create a new allocation or be used inside an `sbatch` script or `salloc` session to launch parallel tasks.

**Synopsis**
`srun [OPTIONS]... EXECUTABLE [ARGS]...`

**Key Options**

* **Task and Resource Specification:**
  * `-N, --nodes=<count>`: Number of nodes for the step.
  * `-n, --ntasks=<count>`: Total number of tasks to launch.
  * `-c, --cpus-per-task=<count>`: Number of CPUs per task. This implies `--exact`.
  * `--gpus-per-task=<count>`: Request a specific number of GPUs for each task.
  * `--distribution=<type>`: Specify how tasks are distributed across nodes (e.g., `block`, `cyclic`).
  * `--exclusive`: Allocate dedicated resources for the step, preventing other steps from sharing CPUs.
  * `--overlap`: Allow a job step to share resources with other steps.
* **Input/Output:**
  * `-o, --output=<file>`: Redirect stdout for all tasks.
  * `-i, --input=<mode>`: Specify stdin redirection.
  * `--label`: Prepend each line of output with the task number.
* **Execution Control:**
  * `--multi-prog`: Run different programs for different tasks using a configuration file.
  * `--pty`: Execute task 0 in a pseudo-terminal.

#### `salloc`

Obtains a SLURM job allocation and typically starts a shell or a specified command within that allocation. It's used for interactive sessions.

**Synopsis**
`salloc [OPTIONS]... [COMMAND]`

**How it Works**
`salloc` blocks until the resource allocation is granted. Once granted, it runs the specified command [or a default shell](cite: 2128). When the command or shell exits, the allocation is relinquished. This is ideal for interactive work, debugging, and compiling.

**Key Options**
`salloc` accepts nearly all the same resource request options as `sbatch`, such as:

* `-N, --nodes=<count>`
* `-n, --ntasks=<count>`
* `-c, --cpus-per-task=<count>`
* `--mem=<size>`
* `-t, --time=<time>`
* `-p, --partition=<name>`
* `-G, --gpus=<count>`
* `--no-shell`: Allocate resources but do not run a command or shell. The allocation can then be used with `srun --jobid=<jobid>`.
* `--x11`: Sets up X11 forwarding for graphical applications.

### Job Monitoring and Control Commands

These commands are used to view and manage the state of jobs and the cluster.

#### `squeue`

Views the status of jobs in the SLURM queue.

**Synopsis**
`squeue [OPTIONS]`

**Key Options**

* `-u, --user=<user>`: Display jobs for a specific user.
* `-j, --jobs=<jobid_list>`: Display information for specific job IDs.
* `-p, --partition=<name>`: Display jobs in a specific partition.
* `-t, --states=<state_list>`: Display jobs in a specific state (e.g., `PENDING`, `RUNNING`).
* `-A, --account=<account>`: Display jobs for a specific account.
* `-l, --long`: Display more detailed information.
* `-s, --steps`: Display job step information.
* `--start`: Show the expected start time for pending jobs.

**Common Job State Codes**

* **PD (PENDING)**: The job is waiting for resource allocation.
* **R (RUNNING)**: The job currently has an allocation.
* **CG (COMPLETING)**: The job is in the process of finishing.
* **CD (COMPLETED)**: The job finished with an exit code of zero.
* **F (FAILED)**: The job terminated with a non-zero exit code.
* **TO (TIMEOUT)**: The job was terminated for exceeding its time limit.
* **CA (CANCELLED)**: The job was explicitly cancelled.

#### `scancel`

Signals or cancels jobs and job steps.

**Synopsis**
`scancel [OPTIONS]... [JOBID[.STEPID]]...`

**Key Options**

* **Job Filtering:**
  * `-n, --name=<name>`: Cancel jobs with a specific name.
  * `-p, --partition=<name>`: Cancel jobs in a specific partition.
  * `-u, --user=<user>`: Cancel jobs owned by a specific user.
  * `-t, --state=<state>`: Cancel jobs in a specific state (usually `PENDING`).
* **Signaling:**
  * `-s, --signal=<signal>`: Send a specific signal (e.g., `SIGSTOP`, `SIGUSR1`) instead of canceling the job.
  * `-f, --full`: Signal all processes associated with a job, including the batch script shell and its children.

#### `sinfo`

Views information about SLURM nodes and partitions.

**Synopsis**
`sinfo [OPTIONS]`

**Key Options**

* `-N, --Node`: Display node-oriented information instead of the default partition view.
* `-l, --long`: Display more detailed information.
* `-s, --summarize`: Display a summary of partition states.
* `-p, --partition=<name>`: Display information for a specific partition.
* `-t, --states=<states>`: Display nodes in a specific state (e.g., `idle`, `alloc`, `drain`).
* `-R, --list-reasons`: List the reasons why nodes are down or drained.

**Common Node State Codes**

* **alloc**: The node is fully allocated.
* **idle**: The node is not allocated and available for use.
* **mix**: The node is partially allocated.
* **drain**: The node is unavailable for new jobs and waiting for running jobs to complete.
* **down**: The node is unavailable for use.

#### `scontrol`

A powerful administrative tool used to view and modify the state of jobs, partitions, nodes, and other SLURM configurations.  **Use with caution.**

**Synopsis**
`scontrol [OPTIONS]... [COMMAND]`

**Key Commands**

* `show job <jobid>`: Display detailed information about a specific job.
* `show node <nodename>`: Display detailed information about a specific node.
* `show partition <name>`: Display detailed information about a partition.
* `update JobId=<jobid> <param>=<value>`: Modify a parameter for a job. Can change time limits, partitions, QOS, etc.
* `hold <jobid>`: Place a pending job into a held state.
* `release <jobid>`: Release a held job.
* `requeue <jobid>`: Requeue a running, suspended, or finished job.

### Accounting and Performance Commands

These commands provide historical data and performance metrics.

#### `sacct`

Displays accounting data for completed and running jobs from the SLURM accounting database or log.

**Synopsis**
`sacct [OPTIONS]`

**Key Options**

* `-j, --jobs=<jobid_list>`: Display accounting data for specific jobs.
* `-u, --user=<user>`: Display jobs for a specific user.
* `-A, --accounts=<account>`: Display jobs for a specific account.
* `-S, --starttime=<time>`: Select jobs that started after a specific time.
* `-E, --endtime=<time>`: Select jobs that ended before a specific time.
* `-o, --format=<fields>`: Specify a comma-separated list of fields to display (e.g., `JobID,User,State,Elapsed,MaxRSS`).
* `-l, --long`: Display a comprehensive set of fields.
* `-X, --allocations`: Display statistics for the job allocation as a whole, not individual steps.

#### `sstat`

Displays status information and performance metrics for running jobs or steps.

**Synopsis**
`sstat [OPTIONS]`

**Key Options**

* `-j, --jobs=<jobid.stepid>`: The specific running job or step to query. This option is required.
* `-a, --allsteps`: Display all running steps for the specified job.
* `-o, --format=<fields>`: Specify a comma-separated list of fields (e.g., `AveCPU,AveRSS,MaxRSS`).
* `-p, --parsable`: Create delimited output suitable for scripting.

### Priority and Fairshare Commands

These commands are used when the multifactor priority plugin is enabled.

#### `sprio`

Views the components that make up a job's scheduling priority.

**Synopsis**
`sprio [OPTIONS]`

**Key Options**

* `-j, --jobs=<jobid>`: Display priority components for a specific job.
* `-l, --long`: Report more detailed information.
* `-w, --weights`: Display the configured weights for each priority factor.

#### `sshare`

Views fair-share data for users and accounts.

**Synopsis**
`sshare [OPTIONS]`

**Key Options**

* `-u, --user=<user>`: Display share information for a specific user.
* `-A, --account=<account>`: Display share information for a specific account.
* `-l, --long`: Include normalized usage information in the output.

### Common Syntactic Elements

#### Filename Patterns

Used in options like `-o` and `-e` to create unique output files for jobs and tasks.

* `%j`: Job ID.
* `%A`: Job array's master job ID.
* `%a`: Job array index number.
* `%N`: Short hostname.
* `%n`: Node identifier relative to the job.
* `%t`: Task identifier.

#### Job Dependency Syntax (`--dependency=<type:jobid>`)

* `afterok:job_id`: Begins after `job_id` completes successfully [exit code 0](cite: 196).
* `afterany:job_id`: Begins after `job_id` terminates for any reason.
* `afternotok:job_id`: Begins after `job_id` terminates with a non-zero exit code.
* `singleton`: Begins after any previously run job with the same name and user has terminated.
