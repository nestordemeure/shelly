### SLURM Job Analysis Example: Diagnosing a Failed Job

This workflow illustrates how to investigate a completed or failed job by correlating SLURM job metadata, node assignment, and system events. It’s aimed at pinpointing whether failures are due to application errors or system issues.

Suppose you are analyzing job **`65537`**.

#### 1. **Check Job Summary**

Use `sacct` to get the job’s final state, exit code, timing, and node assignment:

```bash
sacct --jobs=65537 -o JobID,JobName,User,State,ExitCode,Start,End,NodeList
```

*Key checks:*

* **`State`**: `FAILED`, `CANCELLED`, or `NODE_FAIL` indicate abnormal termination.
* **`ExitCode`**: Non-zero exit codes suggest application-level errors.
* **`Start/End`** and **`NodeList`** will help correlate node events.

Example output:

```
JobID     JobName   User      State   ExitCode  Start                 End                   NodeList
65537     my_sim    user1     FAILED  1:0       2025-07-11T10:00:00   2025-07-11T10:15:00   pm0123
```

#### 2. **Inspect Detailed Job Info**

Get the full job record with `scontrol`:

```bash
scontrol show job 65537
```

*Focus on:*

* **`Command`**: Application invoked.
* **`StdOut` / `StdErr`**: Paths to log files for debugging.
* **`WorkDir`**: Context of job execution.
* **`Reason`**: If `NODE_FAIL` or `TIMEOUT`, investigate further.

#### 3. **Check Node Events**

If the failure hints at a node issue, examine system events for the node during the job’s runtime.

```bash
# Job ran 10:00–10:15; check a slightly wider window:
sacctmgr show event start=2025-07-11T09:55:00 end=2025-07-11T10:20:00 node=pm0123 --parsable2
```

*Key insight:*
Any reported `DRAIN`, `DOWN`, or similar events during the job window indicate system-level causes.

Example:

```
Cluster|NodeName|TimeStart          |State |Reason                   |User
perlmutter|pm0123|2025-07-11T10:12:00|drain |node unexpected reboot   |root
```

Here, the node drained mid-job, likely causing the failure.

#### **Summary**

This workflow isolates failures to:

* **Application errors**: Non-zero `ExitCode`, logs in `StdErr`.
* **System issues**: Node events (`sacctmgr`), hardware faults.
