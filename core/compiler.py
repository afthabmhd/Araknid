import os
import sys
import subprocess
import tempfile
import platform
from PyQt5.QtCore import QObject, pyqtSignal, QProcess, QTimer

class CompilerManager(QObject):
    """Manager for compiling and running C code using GCC (w64devkit)"""
    
    # Signals
    compilation_started = pyqtSignal()
    compilation_finished = pyqtSignal(bool, str)  # Success flag, output
    execution_started = pyqtSignal()
    execution_output = pyqtSignal(str)  # Streaming output
    execution_finished = pyqtSignal(int)  # Exit code
    
    def __init__(self):
        super().__init__()
        
        # Initialize paths and settings based on platform
        self._init_compiler_paths()
        
        # Process management
        self.compile_process = None
        self.run_process = None
        self.temp_dir = None
        self.temp_c_file = None
        self.temp_executable = None
        
    def _init_compiler_paths(self):
        """Initialize compiler paths based on the platform"""
        self.compiler_type = "gcc"  # Default to GCC
        self.compiler_path = None  # Path to the compiler executable
        self.flags = ["-Wall", "-Wextra", "-std=c11"]
        
        # Check system platform
        system = platform.system()
        
        if system == "Windows":
            # Windows paths including w64devkit
            potential_paths = [
                # w64devkit paths
                "C:\\w64devkit\\bin\\gcc.exe",
                "C:\\w64devkit\\gcc.exe",
                # Standard MinGW paths
                "C:\\mingw64\\bin\\gcc.exe",
                "C:\\mingw-w64\\mingw64\\bin\\gcc.exe",
                "C:\\Program Files\\Git\\mingw64\\bin\\gcc.exe",
                # Try current directory
                os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "w64devkit", "bin", "gcc.exe")
            ]
            
            # Try to find gcc in PATH
            try:
                result = subprocess.run(
                    ["where", "gcc"], 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    timeout=2
                )
                if result.returncode == 0:
                    path_output = result.stdout.decode('utf-8').strip()
                    if path_output:
                        first_path = path_output.split('\n')[0].strip()
                        potential_paths.insert(0, first_path)
            except Exception:
                pass
        else:
            # For non-Windows, still try to use Clang first, then GCC
            potential_paths = [
                "/usr/bin/clang",
                "/usr/local/bin/clang",
                "/usr/bin/gcc",
                "/usr/local/bin/gcc"
            ]
        
        # Find the first available compiler executable
        for path in potential_paths:
            if os.path.exists(path) and os.access(path, os.X_OK):
                self.compiler_path = path
                self.compiler_type = "gcc" if "gcc" in path.lower() else "clang"
                break
    
    def is_compiler_available(self):
        """Check if the compiler is available"""
        # First check direct path
        if self.compiler_path and os.path.exists(self.compiler_path):
            return True
            
        # Try to find gcc in PATH
        try:
            if platform.system() == "Windows":
                result = subprocess.run(
                    ["gcc", "--version"], 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    timeout=2
                )
                if result.returncode == 0:
                    self.compiler_path = "gcc"  # Use gcc from PATH
                    self.compiler_type = "gcc"
                    return True
            else:
                # Try clang first, then gcc
                for compiler in ["clang", "gcc"]:
                    try:
                        result = subprocess.run(
                            [compiler, "--version"], 
                            stdout=subprocess.PIPE, 
                            stderr=subprocess.PIPE,
                            timeout=2
                        )
                        if result.returncode == 0:
                            self.compiler_path = compiler  # Use from PATH
                            self.compiler_type = compiler
                            return True
                    except:
                        pass
        except Exception:
            pass
            
        return False
        
    def compile_code(self, code, additional_flags=None):
        """Compile C code using GCC"""
        try:
            self.compilation_started.emit()
            
            if not self.is_compiler_available():
                self.compilation_finished.emit(False, "GCC compiler not found. Please install w64devkit or MinGW-w64 or check your path settings.")
                return
            
            # Create temporary directory and files if needed
            if not self.temp_dir:
                self.temp_dir = tempfile.mkdtemp(prefix="araknid_")
                
            # Create temporary C file
            self.temp_c_file = os.path.join(self.temp_dir, "code.c")
            with open(self.temp_c_file, 'w', encoding='utf-8') as f:
                f.write(code)
                
            # Determine output filename based on platform
            if platform.system() == "Windows":
                self.temp_executable = os.path.join(self.temp_dir, "code.exe")
            else:
                self.temp_executable = os.path.join(self.temp_dir, "code")
                
            # Prepare compilation command
            cmd = [self.compiler_path]
            cmd.extend(self.flags)
            if additional_flags:
                cmd.extend(additional_flags)
            cmd.extend(['-o', self.temp_executable, self.temp_c_file])
            
            # Create and configure process
            if self.compile_process is not None:
                # Ensure any previous process is properly cleaned up
                if self.compile_process.state() != QProcess.NotRunning:
                    self.compile_process.terminate()
                    self.compile_process.waitForFinished(1000)  # Wait for 1 second
                self.compile_process.deleteLater()
                
            self.compile_process = QProcess()
            self.compile_process.setProcessChannelMode(QProcess.MergedChannels)
            self.compile_process.finished.connect(self._handle_compilation_finished)
            
            # Start compilation
            self.compile_process.start(cmd[0], cmd[1:])
            
        except Exception as e:
            # Handle any unexpected errors
            error_message = f"Compilation error: {str(e)}"
            self.compilation_finished.emit(False, error_message)
            if self.compile_process:
                self.compile_process.deleteLater()
                self.compile_process = None
        
    def _handle_compilation_finished(self, exit_code, exit_status):
        """Handle the compilation process finishing"""
        try:
            output = bytes(self.compile_process.readAll()).decode('utf-8', errors='replace')
            
            success = (exit_code == 0 and exit_status == QProcess.NormalExit)
            
            # Clean up for another compilation
            self.compile_process.deleteLater()
            self.compile_process = None
            
            # Emit signal with results
            self.compilation_finished.emit(success, output)
            
        except Exception as e:
            # Handle any unexpected errors
            error_message = f"Error processing compilation results: {str(e)}"
            self.compilation_finished.emit(False, error_message)
            
            if self.compile_process:
                self.compile_process.deleteLater()
                self.compile_process = None
        
    def run_program(self, input_data=None):
        """Run the compiled program"""
        try:
            if not self.temp_executable or not os.path.exists(self.temp_executable):
                self.execution_output.emit("No compiled executable found. Please compile first.")
                self.execution_finished.emit(1)
                return
                
            self.execution_started.emit()
            
            # Create and configure process
            if self.run_process is not None:
                # Ensure any previous process is properly cleaned up
                if self.run_process.state() != QProcess.NotRunning:
                    self.run_process.terminate()
                    self.run_process.waitForFinished(1000)  # Wait for 1 second
                self.run_process.deleteLater()
                
            self.run_process = QProcess()
            self.run_process.setProcessChannelMode(QProcess.MergedChannels)
            
            # Connect signals for streaming output
            self.run_process.readyReadStandardOutput.connect(self._handle_program_output)
            self.run_process.finished.connect(self._handle_program_finished)
            
            # Set working directory to the directory containing the executable
            # This helps with file operations in the program
            self.run_process.setWorkingDirectory(os.path.dirname(self.temp_executable))
            
            # Start the process
            self.run_process.start(self.temp_executable)
            
            # Send input data if provided
            if input_data:
                self.run_process.write(input_data.encode('utf-8'))
                
        except Exception as e:
            # Handle any unexpected errors
            error_message = f"Execution error: {str(e)}"
            self.execution_output.emit(error_message)
            self.execution_finished.emit(1)
            
            if self.run_process:
                self.run_process.deleteLater()
                self.run_process = None
            
    def _handle_program_output(self):
        """Handle output from the running program"""
        try:
            if self.run_process:
                output = bytes(self.run_process.readAll()).decode('utf-8', errors='replace')
                self.execution_output.emit(output)
        except Exception as e:
            self.execution_output.emit(f"Error processing program output: {str(e)}")
            
    def _handle_program_finished(self, exit_code, exit_status):
        """Handle the program execution finishing"""
        try:
            # Read any remaining output
            if self.run_process:
                output = bytes(self.run_process.readAll()).decode('utf-8', errors='replace')
                if output:
                    self.execution_output.emit(output)
                
            # Clean up
            if self.run_process:
                self.run_process.deleteLater()
                self.run_process = None
            
            # Emit finished signal
            self.execution_finished.emit(exit_code)
            
        except Exception as e:
            self.execution_output.emit(f"Error handling program termination: {str(e)}")
            self.execution_finished.emit(1)
            
            if self.run_process:
                self.run_process.deleteLater()
                self.run_process = None
        
    def stop_running_program(self):
        """Stop the currently running program"""
        if self.run_process and self.run_process.state() != QProcess.NotRunning:
            try:
                self.run_process.terminate()
                
                # Force kill after timeout
                QTimer.singleShot(3000, self._force_kill_process)
            except Exception as e:
                self.execution_output.emit(f"Error stopping program: {str(e)}")
            
    def _force_kill_process(self):
        """Force kill the process if it's still running after terminate"""
        if self.run_process and self.run_process.state() != QProcess.NotRunning:
            try:
                self.run_process.kill()
            except Exception as e:
                self.execution_output.emit(f"Error force-killing program: {str(e)}")
            
    def cleanup(self):
        """Clean up temporary files"""
        try:
            # Stop any running processes
            if self.compile_process and self.compile_process.state() != QProcess.NotRunning:
                self.compile_process.terminate()
                self.compile_process.waitForFinished(1000)  # Wait up to 1 second
                
            if self.run_process and self.run_process.state() != QProcess.NotRunning:
                self.run_process.terminate()
                self.run_process.waitForFinished(1000)  # Wait up to 1 second
                
            # Remove temporary files if they exist
            if self.temp_c_file and os.path.exists(self.temp_c_file):
                try:
                    os.remove(self.temp_c_file)
                except Exception:
                    pass
                    
            if self.temp_executable and os.path.exists(self.temp_executable):
                try:
                    os.remove(self.temp_executable)
                except Exception:
                    pass
                    
            # Remove temporary directory
            if self.temp_dir and os.path.exists(self.temp_dir):
                try:
                    # Try to remove the directory
                    os.rmdir(self.temp_dir)
                except Exception:
                    pass
                    
            # Clean up process objects
            if self.compile_process:
                self.compile_process.deleteLater()
            if self.run_process:
                self.run_process.deleteLater()
                
            # Reset variables
            self.temp_c_file = None
            self.temp_executable = None
            self.temp_dir = None
            self.compile_process = None
            self.run_process = None
            
        except Exception as e:
            print(f"Error during cleanup: {e}")  # Print to stdout since we're likely shutting down
