from PyQt5 import QtCore
import os
import platform
import shlex
from subprocess import Popen
import signal
import re
import tempfile
from time import time as epoch_time
import psutil
from operator import itemgetter
# TODO: import PyQt5 if needed: if importlib.util.find_spec("PyQt5") != None:

class CCompiler(QtCore.QThread):
    """ This class receives a root folder. It iterates recursively inside
    folders and tries to check if C++ code exists. If C++ code exists and
    there is no make file it will create the necessary make file for it. This
    class also gives you the ability to execute the code as well in a cross
    platform manner.
    List of Changes:
        v0.0: #inlucde"myfile.h" no space before, " right after include.
        v0.1: #include "myfile.h" now also works.
        v0.3: cross platform capabilities: added nmake support in windows
        """
    # Defining triggers
    log_trigger = QtCore.pyqtSignal(str)

    def __init__(self, root):
        QtCore.QThread.__init__(self)
        self._root = root  # root folder
        self.inc_pat = re.compile(r'^ *#include *"(\w+\.h(?:pp)?)"')
        self.makefiles_path = []  # stores their path to make later
        self._processes = []   # Will hold all the subprocesses
        self._arch = platform.machine()  # x86_64 or i386
        self._env = os.environ.copy()  # environment variables are returned in
        self._plat = platform.system()  # Linux or Windows
        if "Windows" in self._plat:
            self.is_windows = True
            self.is_linux = False
            self.make_cmd = shlex.split("nmake -nologo")
            self.make_clean_cmd = shlex.split("nmake -nologo clean")
        elif "Linux" in self._plat:
            self.is_windows = False
            self.is_linux = True
            self.make_cmd = shlex.split("make")
            self.make_clean_cmd = shlex.split("make clean")

    def change_root(self, root):
        """ It is not needed to destroy the object and create another one. By
        calling this method root is changed while configurations are reused."""
        self._root = root
        self.makefiles_path.clear()  # reset the previous makefiles
        self.kill_windows()   # closes all open windows

    def kill_windows(self):
        """ In this function all the open windows including the pdf viewer,
        editor and terminals should be closed."""
        if self.is_linux:
            for p in self._processes:
                os.killpg(os.getpgid(p.pid), signal.SIGTERM)
            self._processes.clear()
        elif self.is_windows:  # TODO: Add support for windows
            pass

    def generate_makefiles(self):
        """ It will check the folder if proper C++ code exists and a make file is
        needed to be generated. output is logged."""
        for dir_path, dir_names, file_names in os.walk(self._root):
            # There might be a src directory inside the folder, and possibly
            # some c++ sources would be there, so check for this.
            if os.path.isdir(os.path.join(dir_path, "src")):  # if src dir?
                # Now we should check if any cpp exists in src dir
                files = [f.lower() for f in
                         os.listdir(os.path.join(dir_path, "src"))]
                if sum([f.endswith(".cpp") for f in files]) > 0:  # > 1 cpp
                    self._write_makefile(dir_path)
                    self.makefiles_path.append(dir_path)

            # if the top level directory is named src skip it, because there
            # should be a makefile in top level directory (look at previous if)
            elif os.path.basename(dir_path).lower() == "src":
                # Check if cpp exists in this directory, i.e., file_names
                if sum([f.lower().endswith(".cpp") for f in file_names]) > 0:
                    # Now there should be a makefile in toplevel directory
                    top_dir = os.path.dirname(dir_path)
                    top_dir_files = [f.lower() for f in os.listdir(top_dir)]
                    assert "makefile" in top_dir_files

            # Then we should check if a makefile already created by user
            # Here we convert all files to lower case
            elif "makefile" in [f.lower() for f in file_names]:
                self.makefiles_path.append(dir_path)

            # Now check if at least 1 cpp file exists, if yes create
            elif sum([f.lower().endswith(".cpp") for f in file_names]) > 0:
                    self._write_makefile(dir_path)
                    self.makefiles_path.append(dir_path)

    def compile(self):
        """ This method will compile the code using C++ makefiles """
        if len(self.makefiles_path) == 0:
            self.log_trigger.emit("No Makefile to compile.")
            return
        windows_cmd = ""  # Holds the final command to execute for windows
        for makefile_path in self.makefiles_path:
            # Creating two temporary files for stdout and stderr
            out_fd, out_path = tempfile.mkstemp()
            err_fd, err_path = tempfile.mkstemp()
            with os.fdopen(out_fd, 'w') as shell_out:
                with os.fdopen(err_fd, 'w') as shell_err:
                    cur_rel_dir = os.path.relpath(makefile_path, self._root)
                    self.log_trigger.emit(cur_rel_dir + ":")
                    if self.is_linux:
                        p = Popen(self.make_clean_cmd, env=self._env,
                                  cwd=makefile_path, shell=False,
                                  stderr=shell_err, stdout=shell_out)
                        p.wait()  # wait for make clean process to finish
                        p = Popen(self.make_cmd, env=self._env, cwd=makefile_path,
                                  shell=False, stderr=shell_err, stdout=shell_out)
                        p.wait()  # wait for make to finish
                    if self.is_windows:  # Generate command and execute later
                        windows_cmd += "&& cd \"{}\" && nmake clean -nologo && nmake -nologo ".format(makefile_path)
            self.log_trigger.emit(open(out_path, 'r').read())
            self.log_trigger.emit(open(err_path, 'r').read())
            os.remove(out_path)
            os.remove(err_path)

        if self.is_windows:  # here execute the command
            windows_cmd = "\"c:\\Program Files (x86)\\Microsoft Visual Studio 14.0\\VC\\bin\\vcvars32.bat\" " + windows_cmd
            out_fd, out_path = tempfile.mkstemp()
            err_fd, err_path = tempfile.mkstemp()
            with os.fdopen(out_fd, 'w') as shell_out:
                with os.fdopen(err_fd, 'w') as shell_err:
                    p = Popen(shlex.split(windows_cmd), shell=True,
                              stderr=shell_err, stdout=shell_out)
                    p.wait()
                    p.terminate()
            self.log_trigger.emit(open(out_path, 'r').read())
            self.log_trigger.emit(open(err_path, 'r').read())
            os.remove(out_path)
            os.remove(err_path)       

    def exec(self):
        """ This method will execute the executable. It should understand what is
        the executable in different platforms. It also assumes that the
        executables are in the same folder as makefile in Linux"""
        if self.is_windows:
            for makefile_path in self.makefiles_path:
                cur_rel_dir = os.path.relpath(makefile_path, self._root)
                target = list(filter(lambda f: f.lower().endswith(".exe"),
                                      os.listdir(makefile_path)))
                if len(target) > 1:
                    self.log_trigger.emit("More than 1 executable -> Skip")
                    continue
                elif len(target) == 0:
                    self.log_trigger.emit("{}: No executable found -> Check".\
                                          format(cur_rel_dir))
                    continue
                target = target[0]
                self.log_trigger.emit("Exec: {}".format(os.path.join(cur_rel_dir,
                                                                     target)))
                cmd = "start /i cmd /c \"title {} ... & {} & pause\"".format(
                    # e.g. BP-HW1-9523000/2/a in title of command prompt
                    os.path.join(os.path.dirname(self._root), cur_rel_dir),
                    target)
                p = Popen(shlex.split(cmd), shell=True, cwd=makefile_path)
                self._processes.append(p)
                # TODO: Processes should be managed with psutil to kill properly

        elif self.is_linux:
            targets = []   # Holds all the target paths
            for makefile_path in self.makefiles_path:
                cur_rel_dir = os.path.relpath(makefile_path, self._root)
                makefile_name = list(filter(lambda f: f.lower() == "makefile",
                                            os.listdir(makefile_path)))[0]
                makefile_lines = open(os.path.join(makefile_path, makefile_name),
                                      'r').readlines()
                target = list(filter(lambda l: l.strip().upper().startswith(
                    "TARGET"), makefile_lines))
                if len(target) != 1:
                    self.log_trigger.emit("Could not find the target line")
                    continue
                target = target[0].split()[-1]  # the last part of the line
                self.log_trigger.emit("Exec: {}".format(os.path.join(cur_rel_dir,
                                                                     target)))
                targets.append(os.path.join(makefile_path, target))  # full path

            # Now executing the terminal
            terminal_cmd = "gnome-terminal --disable-factory "
            tab_cmd = "--tab --working-directory={} -e " +\
                      """'bash -c "pwd;./{};exec bash" ' """
            cmd = terminal_cmd  # This holds the final command to execute
            for target in targets:
                cmd += tab_cmd.format(os.path.dirname(target),
                                      os.path.basename(target))
            p = Popen(shlex.split(cmd), start_new_session=True)
            self._processes.append(p)

    def find_dep(self, cpp_h_file):
        """ This function finds all the included headers recursively. First
        time cpp is passed but 2nd, 3rd, etc headers are passed.
        User defined header files should be: #include"myfile.h" and
        the rest of the libraries like: #include<xxx> """
        # First we try to know if cpp is passed or .h, since the dirs may differ
        if cpp_h_file.endswith('.cpp'):  # Should we join src folder to its path?
            if self.__root != self._src_dir:  # we have src folder here
                cpp_h_file_path = os.path.join(self.__root, "src", cpp_h_file)
            else:
                cpp_h_file_path = os.path.join(self.__root, cpp_h_file)
        else:  # we have .h file, should we add .inc to its path?
            if self._inc_dir is not None:  # inc folder exists
                cpp_h_file_path = os.path.join(self.__root, "inc", cpp_h_file)
            else:   # inc folder does not exist
                cpp_h_file_path = os.path.join(self.__root, cpp_h_file)
        with open(cpp_h_file_path, 'r') as f:
            src_lines = f.readlines()  # Read whole file into memory
        inc_files = []  # list of include files
        for line in src_lines:
            res = self.inc_pat.match(line)
            if res is not None:
                inc_file = res.group(1)
                if inc_file not in inc_files:
                    inc_files.append(inc_file)
                    inc_files.extend(self.find_dep(inc_file))
        return inc_files

    def _write_makefile(self, root):
        self.__root = root   # save this parameter, it is needed
        # Preamble
        if "Linux" in self._plat:
            make_file = "CXX      = g++\n" + \
                        "LXX      = g++\n" + \
                        "CXXFLAGS = -std=c++17 -Wall -c -g\n" + \
                        "LXXFLAGS = -Wall\n"
        elif "Windows" in self._plat:
            make_file = "CXX      = cl.exe\n" + \
                        "LXX      = link.exe\n" + \
                        "CXXFLAGS = -nologo /EHs /O2 /Ot /GA /c\n" + \
                        "LXXFLAGS = -nologo\n"
            
        # if inc folder exists include it otherwise put variable to None
        self._inc_dir = os.path.join(self.__root, "inc")
        if os.path.exists(self._inc_dir):
            if os.path.isdir(self._inc_dir):
                if "Linux" in self._plat:
                    make_file = make_file.replace("-c", "-I ./inc -c")
                elif "Windows" in self._plat:
                    make_file = make_file.replace("/c", "/Iinc\ /c")
            else:
                self._inc_dir = None
        else:
            self._inc_dir = None

        # if src folder exists include it otherwise put __root as src
        self._src_dir = os.path.join(self.__root, "src")
        if os.path.exists(self._src_dir):
            if not os.path.isdir(self._src_dir): # src exists but it is not dir
                self._src_dir = self.__root
        else:  # src does not exist
            self._src_dir = self.__root

        # Note that many other files may exist other than cpp files
        src_files = [f for f in os.listdir(self._src_dir) if f.endswith(".cpp")]
        


        # Writing OBJECTS = line
        dep_dic = dict()
        if "Windows" in self._plat:
            obj_ext = "obj"
        elif "Linux" in self._plat:
            obj_ext = "o"
        object_files = [src[:-3] + obj_ext for src in src_files]
        object_line = "OBJECTS  = "
        for obj_file in object_files:
            object_line = object_line + "obj" + os.sep + obj_file + " "
        make_file += object_line + "\n"        

        # Writing TARGET =  line
        if "Windows" in self._plat:
            make_file += "TARGET   = main.exe\n\n"
        elif "Linux" in self._plat:
            make_file += "TARGET   = main\n\n"
        
        # Writing first section of MakeFile
        make_file += "$(TARGET): $(OBJECTS)\n" + \
                        "\t$(LXX) $(LXXFLAGS) $(OBJECTS) -o $(TARGET)\n" + \
                        "\t@echo \"Linking complete!\"\n\n"
        if self.is_windows:
            make_file = make_file.replace("-o $(TARGET)", "/out:$(TARGET)")

        # Finding Dependency list
        for src_file in src_files:
            dep_dic[src_file] = self.find_dep(src_file)
        # Writing 2 lines per each object file: 4 cases
        # 1 : both src and inc exist
        # 2 : src exists but not inc
        # 3 : inc exists but not src
        # 4 : neither exists
        for index, obj in enumerate(object_files):
            src = obj.rstrip(obj_ext) + "cpp"  # main source file for object file
            if self._src_dir != self.__root:   # src exists
                if self._inc_dir is not None:  # both src and inc exist
                    first_line = "obj" + os.sep + obj + ": src" + os.sep + src \
                                 + ' ' + " ".join(["inc" + os.sep + header for
                                                   header in dep_dic[src]]) + '\n'
                    if self.is_linux:
                        second_line = "\t$(CXX) $(CXXFLAGS) src/" + src\
                                      + " -o " + "obj" + os.sep + obj + '\n'
                    elif self.is_windows:
                        second_line = "\t$(CXX) $(CXXFLAGS) -Foobj" + os.sep + \
                                      " " + src
                else:                     # only src exists
                    first_line = "obj" + os.sep + obj + ": src" + os.sep + src\
                                 + ' ' + ' '.join(dep_dic[src]) + '\n'
                    if self.is_linux:
                        second_line = "\t$(CXX) $(CXXFLAGS) src/" + src + \
                                      " -o " + "obj/" + obj + '\n'
                    elif self.is_windows:
                        second_line = "\t$(CXX) $(CXXFLAGS) -Foobj\\ src\\" + \
                                      src + "\n"
            
            # Note that second_line is the same for both cases below
            elif self._inc_dir is not None:  # only inc exists
                first_line = "obj" + os.sep + obj + ": " + src + ' ' + ' '.join(
                    ["inc" + os.sep + header for header in dep_dic[src]]) + '\n'
                if self.is_linux:
                    second_line = "\t$(CXX) $(CXXFLAGS) " + src + " -o " + \
                                  "obj/" + obj + '\n'
                elif self.is_windows:
                    second_line = "\t$(CXX) $(CXXFLAGS) -Foobj\\" + " " + src
            else:  # neither exists
                first_line = "obj" + os.sep + obj + ": " + src + ' ' + ' '.join(
                    [' ' + header for header in dep_dic[src]]) + '\n'
                if self.is_linux:
                    second_line = "\t$(CXX) $(CXXFLAGS) " + src + " -o " + \
                                  "obj/" + obj + '\n'
                elif self.is_windows:
                    second_line = "\t$(CXX) $(CXXFLAGS) -Foobj\\" + " " + src
            # The part between first and second line is to make obj directory
            make_file += first_line
            if self.is_linux:
                make_file += "\t@mkdir -p obj\n"
            elif self.is_windows:
                make_file += "\t@if not exist obj mkdir obj\n"
            make_file += second_line + "\n"

        # Writing make clean part
        if self.is_linux:
            make_file += "\nclean:\n" + \
                         "\trm -fv $(TARGET) $(OBJECTS)\n" + \
                         "\trm -rfv obj\n"
        elif self.is_windows:
            make_file += "\nclean:\n" + \
                         "\tif exist $(TARGET) del /F /S /Q $(TARGET)\n" + \
                         "\tif exist obj rmdir /S /Q obj\n"

        # Writing Makefile
        with open(os.path.join(self.__root, "Makefile"), 'w') as f_handle:
            f_handle.write(make_file)
        self.log_trigger.emit("Makefile generated in: {}".
                              format(os.path.relpath(self.__root, self._root)))

class MATCompiler(QtCore.QThread):
    """ This class receives a root folder. It iterates recursively inside folders
    and tries to check if any .m file exists. Then it checks if the file is a
    script not function by looking at the first line of it. If it did not find
    the function keyword and it had not started with %, then it can be executed.
    List of Changes:
        v0.0: first release
        v0.2: matlab process management implemented in windows, not tested yet
        v0.3: psutil process management in windows tested and working fine
    """
    # Defining triggers
    log_trigger = QtCore.pyqtSignal(str)

    def __init__(self, root):
        QtCore.QThread.__init__(self)
        self._root = root
        self.script_files = []   # Hold all the matlab script files
        self._processes = []  # Holds all the subprocesses
        self._arch = platform.machine()  # x86_64 or i386
        self._env = os.environ.copy()  # environment variables are returned in
        self._plat = platform.system()  # Linux or Windows
        self._comment_re = re.compile(r"^ *%")
        if "Windows" in self._plat:
            self.is_windows = True
            self.is_linux = False
        elif "Linux" in self._plat:
            self.is_windows = False
            self.is_linux = True

    def change_root(self, root):
        """ It is not needed to destroy the object and create another one. By
                calling this method root is changed while configurations are reused."""
        self._root = root
        self.script_files.clear()  # reset the previous makefiles
        self.kill_windows()  # closes all open windows

    def kill_windows(self):
        """ In this function all the open windows including the pdf viewer,
        editor and terminals should be closed."""
        if self.is_windows:
            for p in self._processes:
                if psutil.pid_exists(p.pid): # may be colsed already by user
                    p.terminate()

        elif self.is_linux:
            for p in self._processes:
                if "Linux" in self._plat:
                    os.killpg(os.getpgid(p.pid), signal.SIGTERM)
        
        self._processes.clear()

    def search_scripts(self):
        for dir_path, _, file_names in os.walk(self._root):
            # Filter out all the non .m files
            for mat_file in filter(lambda f: f.lower().endswith('.m'),
                                   file_names):
                # Now filter out script files
                mat_file_fullname = os.path.join(dir_path, mat_file)
                for line in open(mat_file_fullname).readlines():
                    if line.isspace():
                        continue
                    elif 'function' in line:
                        break
                    elif self._comment_re.match(line) is not None:  # comment
                        continue
                    else:  # The .m file is script, so save it
                        self.script_files.append(mat_file_fullname)
                        break
        return self.script_files

    def exec(self):
        if self.is_windows:
            # TODO: Call scripts one after another
            terminal_cmd = """matlab -nodesktop -nosplash -r " """
            q_cmd = """ cd('{}'),disp(pwd),input('press any key to run...','s'),{},"""
            # The for loop should be made, now it is wrong, the code after is OK
            for script_file in self.script_files:
                # Note that .m should be removed from the filename to run
                terminal_cmd += q_cmd.format(os.path.dirname(script_file),
                                             os.path.basename(script_file[:-2]))
                self.log_trigger.emit("Exec: {}".format(os.path.relpath(script_file,
                    self._root)))
            terminal_cmd.rstrip(',')  # remove trailing ,
            terminal_cmd += "\""
            t = epoch_time()
            p = Popen(shlex.split(terminal_cmd))
            # In some computers p.wait() p.terminate() does not do anything
            # in other systems, it blocks the program.
            #p.wait()
            #p.terminate()  # Note that this does not close MATLAB
            # Use psutil to retrieve all the processes with MATLAB
            matlab_proc = list(filter(lambda p: "matlab" in p.name().lower(),
                     psutil.process_iter()))
            # Sometimes more than one matlab process exist
            if len(matlab_proc) > 1:
                diff_time = [abs(p.create_time()-t) for p in matlab_proc]
                # Find the process created almost the same time as t,
                # Hopefully this is correct always
                ind_min = min(enumerate(diff_time), key=itemgetter(1))[0]
                self._processes.append(matlab_proc[ind_min])
            elif len(matlab_proc) > 0:  # In fact should be 1
                self._processes.append(matlab_proc[0])

        elif self.is_linux:  # Here the scripts should be run
            terminal_cmd = "gnome-terminal --disable-factory "
            tab_cmd = "--tab --working-directory='{}' -e " + \
                      """'bash -c "matlab -nodesktop -nosplash -r "{}";""" + \
                      """exec bash" ' """
            cmd = terminal_cmd
            for script_file in self.script_files:  # script_file is absolute path
                # Note that .m should be removed from the command of matlab
                matlab_cmd = script_file[:-2]
                cmd += tab_cmd.format(os.path.dirname(script_file),
                                      os.path.basename(matlab_cmd))
                rel_script_path = os.path.relpath(script_file, self._root)
                self.log_trigger.emit("Exec: {}".format(rel_script_path))
            p = Popen(shlex.split(cmd), shell=False, start_new_session=True)
            self._processes.append(p)