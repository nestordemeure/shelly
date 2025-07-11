### **Job Analysis Workflow Example**

This workflow demonstrates how to manually investigate a completed or failed job by gathering details about its execution, the nodes it ran on, and any relevant system events that occurred during its runtime. This process is useful for diagnosing why a job might have failed unexpectedly.

Let's assume you want to analyze your job that was assigned the ID **`65537`**.

#### **Step 1: Get Basic Job Status and Details**

First, find your job to see its final state and get high-level details. While `squeue` is for active jobs, the **`sacct`** command is best for post-mortem analysis.

* **Command:** Use `sacct` to find your job.

    ```bash
    sacct --jobs=65537 -o JobID,JobName,User,State,ExitCode,Start,End,NodeList
    ```

* **Analysis:** Look at the `State` and `ExitCode`. A `FAILED` state or a non-zero `ExitCode` indicates a problem. Note the `Start` and `End` times, as well as the `NodeList`.

    ```
    JobID     JobName      User      State      ExitCode    Start             End               NodeList
    --------- ------------ --------- ---------- --------    ------------------- ------------------- --------
    65537     my_sim       username  FAILED     1:0         2025-07-11T10:00:00 2025-07-11T10:15:00  pm0123
    ```

#### **Step 2: Get Exhaustive Job Information**

Next, get all the details SLURM has on the job. This includes the full submission script and constraints.

* **Command:** Use `scontrol show job`.

    ```bash
    scontrol show job 65537
    ```

* **Analysis:** This command provides dozens of lines of information. Pay special attention to:
  * **`Command`**: The application that was run.
  * **`WorkDir`**: The working directory.
  * **`StdOut`/`StdErr`**: The location of your output and error files, which are crucial for debugging.
  * **`Reason`**: If the job failed, this may show `NodeFail` or `TimeLimit`.
  * **`NodeList` / `Contiguous`**: The exact nodes used.

#### **Step 3: Check for Node-Level Events**

A common reason for mysterious job failures is an issue with the hardware itself. You can check for events like a node being drained or failing during your job's execution window.

* **Command:** Use `sacctmgr` to show events for the specific node (`pm0123`) around the time the job ran. Add a small buffer (e.g., 5-10 minutes) around the job's `Start` and `End` times.

    ```bash
    # Job ran from 10:00 to 10:15. We'll check from 09:55 to 10:20.
    sacctmgr show event start=2025-07-11T09:55:00 end=2025-07-11T10:20:00 node=pm0123 --parsable2
    ```

* **Analysis:** Look for any output. If the command returns information, it means an event occurred on that node in the time window.

    ```
    Cluster|NodeName|TimeStart|TimeEnd|State|Reason|User
    perlmutter|pm0123|2025-07-11T10:12:00||drain|node unexpected reboot|root
    ```

    This output is a strong indicator that the job failed because the node it was running on was drained by an administrator at `10:12`, which was during the job's execution.

By following this workflow, you can often pinpoint whether a job failure was due to an application error (found in your `StdErr` file) or a system/hardware issue.
