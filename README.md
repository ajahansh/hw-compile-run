# HW-Compile-Run
Automatically compile and run C++, Python and MATLAB files. Used for the instructor to quickly compile and check the assignments.

# How to Use
* Drag the folder containing the zip files in to the table on top left. 
* If the file names match BP-HW#-StNum.zip for example, it will unzip, go inside and look for the question folders. If the structure of the folder is OK, it will show you the question names and report name.
* By clicking on one of the cells in the table you can see the contents of the folder in the file browser below. Click on “open pdf” or “open code” to view the report and code, respectively. 
* After clicking compile, a makefile is generated and all the codes are compiled using make or nmake in windows and linux, respectively. It takes abit longer in Windows to compile. All the questions are compiled according to the order written in the blue terminal window.
* By clicking run, all the programs are run. In Linux they will run in a single gnome-terminal with multiple tabs but in windows multiple command windows will be shown.  Note that matlab and python projects only have run not compile for obvious reasons.
* By changing the active homework, all the open windows corresponding to that homework including, code editor, terminal and pdf viewer are automatically closed. This feature is not yet completely available in windows. 
* In Windows MATLAB files can be run without problems. The program closes the matlab command window once the selected cell is changed.

# Debug
* Windows Only: If you keep the homework files open and rerun the program, the program closes unexpectedly. This problem cannot be solved easily as it is a fundamental limitation in Windows. Open files can not be recreated. 
* After opening a homework in code editor you can change the code and recompile using the designed dialog button. This is useful for example for removing the errors. Try not to drag the folder again to the dialog as it might close unexpectedly, for the reason mentioned above.

# Requirements
* Python 3 with all the needed libraries (preferably use Anaconda)
* Pyqt5, qt5
* PDF Viewer: for windows it is set on Adobe Acrobat. If you need another one please modify the variable self.pdf_viewer: Note the extra leading and trailing double quotation (“)
* Code Viewer: Sublime text 3 is chosen. If you have 32 bit system please modify the variable self.editor. It is better to set hot_exit to false in user preferences.

# SublimeText 3 Instructions
* By default the python program looks for sublimetext3 folder in your computer. The settings in my computer are:
  * `"font_size": 13,`
  * `"hot_exit": false,`
  * `"ignored_packages":`
  * `"remember_open_files": false`

# MATLAB Instructions
* Windows: Note that matlab.exe should be in your system environment variables. To check if it is there run command window and they type matlab and enter.

# TODO
* Using `moss` to check for plagarism.