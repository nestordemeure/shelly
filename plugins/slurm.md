# SLURM: Simple Linux Utility for Resource Management

SLURM is the workload manager used on high-performance computing clusters. It provides commands to submit, monitor, and control computational jobs.

### `sbatch`
Submit batch jobs - queues script for later execution with resource allocation

### `srun`  
Run parallel jobs immediately - executes commands with resource allocation

### `salloc`
Get interactive allocation - provides shell session with allocated resources

### `squeue`
View job queue status - shows pending, running, and completing jobs

### `sinfo`
View cluster information - displays node and partition states

### `scontrol`
Administrative control - view and modify job/node/partition details

### `scancel`
Cancel jobs - terminate pending or running jobs by ID or criteria

### `sacct`
Job accounting data - historical information about completed jobs

### `sstat`
Running job statistics - performance metrics for active jobs

### `sprio`
Job priority breakdown - shows scheduling priority components

### `sshare`
Fair-share information - displays user/account usage and shares

**IMPORTANT**: ALWAYS check the man page for SLURM commands before using them to understand current system-specific options and syntax.
