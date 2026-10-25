using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

[assembly: System.Reflection.AssemblyTitle("EchoCue Standard")]
[assembly: System.Reflection.AssemblyProduct("EchoCue Standard")]

internal static class Launcher
{
    [STAThread]
    private static int Main(string[] args)
    {
        string folder = AppDomain.CurrentDomain.BaseDirectory;
        bool check = args.Length == 1 && args[0] == "--check";
        try
        {
            if (Directory.Exists(Path.Combine(folder, "_internal", "app"))) folder = Path.Combine(folder, "_internal");
            string script = Path.Combine(folder, "app", "launch.pyw");
            if (!File.Exists(script))
                throw new FileNotFoundException("Cannot find app\\launch.pyw. Keep the EXE in the EchoCue folder; use a desktop shortcut.");
            string python = Path.Combine(folder, "runtime", "python", "pythonw.exe");
            if (!File.Exists(python)) python = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                                         "Python", "pythoncore-3.14-64", "pythonw.exe");
            if (!File.Exists(python))
            {
                python = null;
                foreach (string entry in (Environment.GetEnvironmentVariable("PATH") ?? "").Split(';'))
                {
                    string candidate = Path.Combine(entry.Trim().Trim('"'), "pythonw.exe");
                    if (File.Exists(candidate)) { python = candidate; break; }
                }
            }
            if (python == null)
                throw new FileNotFoundException("Python runtime not found. Install the required Python environment and dependencies.");
            if (check) return 0;
            ProcessStartInfo info = new ProcessStartInfo(python, "\"" + script + "\"");
            info.WorkingDirectory = folder;
            info.UseShellExecute = false;
            info.CreateNoWindow = true;
            info.EnvironmentVariables.Remove("PYTHONHOME");
            info.EnvironmentVariables.Remove("PYTHONPATH");
            info.EnvironmentVariables["PYTHONDONTWRITEBYTECODE"] = "1";
            using (Process process = Process.Start(info)) { }
            return 0;
        }
        catch (Exception error)
        {
            if (!check) MessageBox.Show(error.Message, "EchoCue - Startup failed", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
    }
}
