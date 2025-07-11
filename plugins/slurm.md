## SLURM: Simple Linux Utility for Resource Management**

SLURM is the queueing system used to manage and schedule jobs on Perlmutter. It provides a suite of commands to submit, monitor, and control computational work.

### **sbatch: Submit a Batch Job**

The sbatch command is used to submit a non-interactive job script to the SLURM controller. The script typically contains resource requests and the commands to be executed.

**Key Concepts:**

* **Job Script:** A standard shell script (e.g., bash) with special \#SBATCH directives at the top to request resources.  
* **Asynchronous Execution:** sbatch exits immediately after submitting the script, providing a job ID. The job runs later when resources become available.  
* **Output Files:** By default, standard output and error are written to a file named slurm-%j.out, where %j is the job ID.

**Common Options (can be used in script with \#SBATCH or on the command line):**

| Option | Long Option | Description |
| :---- | :---- | :---- |
| \-J \<name\> | \--job-name=\<name\> | Assign a name to the job. |
| \-N \<count\> | \--nodes=\<count\> | Request a specific number of nodes. |
| \-n \<count\> | \--ntasks=\<count\> | Request a specific number of tasks (often MPI ranks). |
| \-c \<cpus\> | \--cpus-per-task=\<cpus\> | Request a number of CPUs for each task (for multithreading). |
| \-t \<time\> | \--time=\<time\> | Set a time limit for the job (e.g., HH:MM:SS, D-HH:MM). |
| \-p \<name\> | \--partition=\<name\> | Submit the job to a specific partition (queue). |
| \-A \<account\> | \--account=\<account\> | Charge the job to a specific account/project. |
| \-o \<file\> | \--output=\<file\> | Specify the standard output file. Use %j for job ID, %a for array index. |
| \-e \<file\> | \--error=\<file\> | Specify the standard error file. |
| \--gpus=\<num\> | \--gpus=\<num\> | Request a total number of GPUs for the job. |
| \--gpus-per-node=\<num\> | \--gpus-per-node=\<num\> | Request a specific number of GPUs on each node. |
| \-C \<features\> | \--constraint=\<features\> | Request nodes with specific features (e.g., gpu). |
| \-a \<indexes\> | \--array=\<indexes\> | Submit a job array (e.g., 0-15, 1,5,10-20%4). |

**Example sbatch Script:**

\#\!/bin/bash  
\#SBATCH \--job-name=my\_simulation  
\#SBATCH \--nodes=4  
\#SBATCH \--ntasks-per-node=32  
\#SBATCH \--cpus-per-task=2  
\#SBATCH \--time=01:30:00  
\#SBATCH \--account=my\_project  
\#SBATCH \--partition=gpu  
\#SBATCH \--gpus-per-node=4  
\#SBATCH \--constraint=gpu

\# Load necessary modules  
module load a\_scientific\_library

\# Run the parallel application  
srun my\_parallel\_executable \--input-file data.in

**To submit this script:** sbatch my\_script.sh

### **srun: Run a Parallel Job Step**

The srun command is used to launch parallel tasks across the resources allocated to a job. It can be used within an sbatch script to run the main application or interactively within an salloc session.

**Key Concepts:**

* **Job Step:** A command executed by srun within a job's resource allocation. A single job can have multiple job steps.  
* **Task Distribution:** srun is responsible for distributing the specified number of tasks across the allocated nodes and CPUs.

**Common Options:**

| Option | Long Option | Description |
| :---- | :---- | :---- |
| \-n \<count\> | \--ntasks=\<count\> | Launch a specific number of tasks. |
| \-N \<count\> | \--nodes=\<count\> | Use a specific number of nodes from the allocation for this step. |
| \-c \<cpus\> | \--cpus-per-task=\<cpus\> | Allocate a number of CPUs for each task. |
| \--cpu-bind=\<type\> |  | Specifies how tasks should be bound to CPUs (e.g., cores, threads). |
| \--gpus-per-task=\<num\> |  | Allocate a specific number of GPUs for each task. |
| \-l | \--label | Prepend the task number to each line of its output. |
| \--multi-prog |  | Run a different program for each task, specified in a configuration file. |

**Example srun usage:**

* **Inside an sbatch script (as seen above):** srun ./my\_program  
* **Interactively (within an salloc shell):** srun \-n 64 \-N 2 \--gpus-per-task=1 ./gpu\_program

### **salloc: Allocate Resources Interactively**

The salloc command allocates resources and typically starts a shell on one of the allocated nodes. This is useful for interactive work, debugging, and compiling. All sbatch resource request options (-N, \-n, \-t, etc.) apply to salloc.

**Workflow:**

1. Request resources with salloc.  
2. Wait for the allocation to be granted.  
3. A new shell prompt appears on a compute node.  
4. Use srun to launch parallel tasks within this shell.  
5. Type exit to relinquish the allocation.

**Example salloc Session:**

\# Request 2 nodes for 30 minutes from the debug partition  
$ salloc \-N 2 \-t 00:30:00 \-p debug \-A my\_project

salloc: Granted job allocation 65537  
\# The user is now in a shell on one of the compute nodes

\# Run a command across the 2 allocated nodes (64 tasks total)  
$ srun \-n 64 hostname  
node01  
node01  
...  
node02  
...

\# When finished, exit the shell to release the resources  
$ exit  
salloc: Relinquishing job allocation 65537

### **squeue: View the Job Queue**

The squeue command displays the status of jobs in the queue.

**Common Options:**

| Option | Long Option | Description |
| :---- | :---- | :---- |
| \-u \<user\> | \--user=\<user\> | Show jobs for a specific user. |
| \--me |  | A shortcut to show only your own jobs. |
| \-p \<name\> | \--partition=\<name\> | Show jobs in a specific partition. |
| \-j \<jobid\> | \--jobs=\<jobid\> | Show information for a specific job ID. |
| \-t \<states\> | \--states=\<states\> | Show jobs in specific states (e.g., PENDING, RUNNING). |
| \-l | \--long | Show more detailed information. |
| \--start |  | Show the expected start time for pending jobs. |

**Job State Codes:**

| Code | State | Description |
| :---- | :---- | :---- |
| PD | PENDING | Job is waiting for resource allocation. |
| R | RUNNING | Job is currently running. |
| CG | COMPLETING | Job is finishing up. |
| CD | COMPLETED | Job finished successfully. |
| F | FAILED | Job terminated with a non-zero exit code. |
| CA | CANCELLED | Job was cancelled by the user or admin. |
| TO | TIMEOUT | Job was terminated for exceeding its time limit. |

### **scancel: Cancel a Job**

The scancel command is used to cancel pending or running jobs.

**Common Options:**

| Option | Long Option | Description |
| :---- | :---- | :---- |
| \<job\_id\> |  | Cancel the specified job ID. |
| \<job\_id\>\_\<array\_id\> |  | Cancel a specific task within a job array. |
| \-u \<user\> | \--user=\<user\> | Cancel jobs belonging to a specific user. |
| \-n \<name\> | \--name=\<name\> | Cancel jobs with a specific name. |
| \-t \<state\> | \--state=\<state\> | Cancel jobs in a specific state (e.g., PENDING). |

**Examples:**

* scancel 65537 (Cancels a single job)  
* scancel 65538\_4 (Cancels task 4 of job array 65538\)  
* scancel \-u username \-t PENDING (Cancels all pending jobs for username)

### **scontrol: View and Modify SLURM State**

A powerful administrative and user command to view detailed information about jobs, nodes, and partitions, and to modify job parameters.

**Common User Commands:**

* scontrol show job \<job\_id\>: Shows exhaustive details about a specific job.  
* scontrol show node \<node\_name\>: Shows details about a specific node.  
* scontrol show partition \<partition\_name\>: Shows details about a specific partition.  
* scontrol hold \<job\_id\>: Places a pending job in a user-held state.  
* scontrol release \<job\_id\>: Releases a user-held job.  
* scontrol update JobId=\<job\_id\> TimeLimit=\<new\_time\>: Update a parameter of a pending or running job.

### **sinfo: View Node and Partition Information**

The sinfo command provides a summary of the state of partitions and the nodes within them.

**Common Options:**

| Option | Long Option | Description |
| :---- | :---- | :---- |
| \-s | \--summarize | Provides a compact summary of nodes per partition. |
| \-N | \--Node | Displays information in a node-oriented format. |
| \-l | \--long | Shows more detailed information. |
| \-p \<name\> | \--partition=\<name\> | Restricts output to a specific partition. |
| \-t \<states\> | \--states=\<states\> | Show nodes in specific states (e.g., idle, alloc, drain). |

**Example:** sinfo \-p gpu \-o "%10P %.12N %.6D %10T %20C" (Shows partition, nodelist, node count, state, and CPU info for the gpu partition).
