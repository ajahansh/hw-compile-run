# coding=<UTF-16>
import PyQt5
import sys
import os
import platform
import re
import shlex
import signal
from PyQt5 import uic
from PyQt5 import QtCore
from PyQt5.QtCore import QModelIndex, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (QApplication, QMainWindow, QTableWidgetItem,
                             QTableWidget, QVBoxLayout, QFileSystemModel)
from ziphandle import ZipHandle
from autocompiler import CCompiler, MATCompiler
from subprocess import Popen
from operator import methodcaller
from IPython import embed


class MyTable(QTableWidget):
    dropped_trigger = QtCore.pyqtSignal(str)

    def __init__(self, parent):
        QTableWidget.__init__(self, parent)
        self.setAcceptDrops(True)

    def dragMoveEvent(self, event):
        event.accept()

    def dragEnterEvent(self, event):
        event.accept()

    def dropEvent(self, event):
        self.dropped_trigger(event.mimeData().text())
        event.accept()

Form = uic.loadUiType('gui.ui')[0]  # Load ui


class MyWindow(QMainWindow, Form):
    def __init__(self):
        Form.__init__(self)
        QMainWindow.__init__(self)
        self.setupUi(self)

        self.setWindowTitle("Automated Homework Correction")

        # Initializations for the student table on the left
        self.st_table = MyTable(self)
        self.st_tab_ind = None  # stores the table col. index/text
        self.persian_font = QFont()  # Holds the persian font for the table
        self.setup_st_table()
        QVBoxLayout(self.table_frame).addWidget(self.st_table)

        # Initializations for the Terminal in Terminal tab
        self.setup_terminal()

        # Initializations for the part below terminal
        self.open_code_push_button.clicked.connect(self.open_code)
        self.open_report_push_button.clicked.connect(self.open_report)
        self.compile_push_button.clicked.connect(self.compile_hw)
        self.run_push_button.clicked.connect(self.run_hw)
        self.prog_type_combo.activated.connect(self.prog_type_changed)
        self.sel_prog_type = self.prog_type_combo.currentText()

        # Initializations for the Folder Tree in Folder Tab
        self.folder_model = QFileSystemModel()
        self.setup_folder_tree_view()

        # Miscellaneous initializations
        self.command = ""  # holds the text in console textbox
        self.hw_path = ""  # holds the dropped hw folder path
        self.sel_hw_path = ""  # path of selected hw in the student table
        self.sel_cn = ""  # Selected course name in the cell
        self.sel_hw_num = 0  # hw num of selected cell
        self.sel_st_num = 0  # student number of selected cell
        self.hw_folders = []  # proper and valid homework folders
        self.prev_row = -1  # holds the previous selected row of table
        self.sep = "----------------------------------------------------"
        self.hw_re = re.compile(r"\A(\w{2})[-_](HW(\d+)[-_](\d{7}))\Z",
                                re.IGNORECASE)
        self.sel_folder_index = None  # index of the folder model for treeView

        self.zip_thread = None  # will hold the ZipHandle Thread

        # Compiler initializations
        self.c_comp = CCompiler(None)   # will hold the C Compiler handle
        self.c_comp.log_trigger.connect(self.compile_box_update)
        self.mat_compiler = MATCompiler(None)
        self.mat_compiler.log_trigger.connect(self.compile_box_update)

        # OS Specific Initializations
        self._processes = []  # holds all active processes for Popen
        self._plat = platform.system()  # Linux or Windows
        self.system_arch = platform.machine()  # x86_64 or i386

        if "Windows" in self._plat:
            self.is_linux = False   # Used later to know if on linux
            self.is_windows = True
            # Windows code editor
            self.editor = "\"C:\\Program Files\\Sublime Text 3\\subl.exe\" --wait"
            self.terminal_cmd = r"C:\Windows\System32\cmd.exe /k"
            self.pdf_viewer = "\"C:\Program Files (x86)\Adobe\Acrobat DC\Acrobat\Acrobat.exe\""
        
        elif "Linux" in self._plat:
            self.is_linux = True
            self.is_windows = False
            self.editor = "/usr/bin/subl --wait"
            self.pdf_viewer = "/usr/bin/evince"
            self.terminal_cmd = None
        else:
            print("Not a standard OS: use Windows or Linux.")

    def setup_st_table(self):
        """ This function is for setting up the table on the left
            of the dialogue. All initializations are made here."""
        self.st_table.dropped_trigger = self.process_hw  # file/folder dropped
        self.st_table.cellClicked.connect(self.hw_clicked)  # a cell is clicked

        self.st_table.setSelectionMode(PyQt5.QtWidgets.QAbstractItemView.
                                       SingleSelection)
        self.st_table.setSelectionBehavior(PyQt5.QtWidgets.QAbstractItemView.
                                           SelectRows)
        # start out with 5 columns
        self.st_tab_ind = {"CN": 0, "HW_Num": 1, "St_Num": 2, "St_Name": 3,
                           "Folders": 4, "Report": 5}
        self.st_table.setColumnCount(len(self.st_tab_ind))
        # Now put text for the columns and set width if required
        self.st_table.setHorizontalHeaderItem(self.st_tab_ind["CN"],
                                              QTableWidgetItem("CN"))
        self.st_table.setColumnWidth(self.st_tab_ind["CN"], 30)
        self.st_table.setHorizontalHeaderItem(self.st_tab_ind["HW_Num"],
                                              QTableWidgetItem("HW"))
        self.st_table.setColumnWidth(self.st_tab_ind["HW_Num"], 31)
        self.st_table.setHorizontalHeaderItem(self.st_tab_ind["St_Num"],
                                              QTableWidgetItem("St. Num"))
        self.st_table.setColumnWidth(self.st_tab_ind["St_Num"], 70)
        self.st_table.setHorizontalHeaderItem(self.st_tab_ind["St_Name"],
                                              QTableWidgetItem("St. Name"))
        self.st_table.setColumnWidth(self.st_tab_ind["St_Name"], 105)
        self.st_table.setHorizontalHeaderItem(self.st_tab_ind["Folders"],
                                              QTableWidgetItem("Folders"))
        self.st_table.setColumnWidth(self.st_tab_ind["Folders"], 100)
        self.st_table.setHorizontalHeaderItem(self.st_tab_ind["Report"],
                                              QTableWidgetItem("Report"))
        self.st_table.setColumnWidth(self.st_tab_ind["Report"], 100)

        self.persian_font.setFamily("XW Zar")  # Persian font setup for the table
        self.persian_font.setPointSize(11)

    def setup_terminal(self):
        self.compile_box.setTextColor(QColor(237, 238, 240))
        self.compile_box.setText("Drag your folder to the table ...")

    def setup_folder_tree_view(self):
        self.folder_tree_view.setModel(self.folder_model)
        self.folder_tree_view.doubleClicked.connect(self.open_file_folder)
        self.folder_tree_view.expanded.connect(self.expanded)
        self.folder_tree_view.setColumnWidth(0, 350)
        self.folder_tree_view.setColumnWidth(1, 50)
        self.folder_tree_view.setColumnWidth(2, 50)
        self.folder_tree_view.hideColumn(3)

    def enable_config(self, yes):
        """ This functions enables the config part if yes is true """
        items = [self.open_code_push_button, self.run_push_button,
                 self.open_report_push_button, self.compile_push_button,
                 self.prog_type_combo]
        if yes:
            method = methodcaller('setEnabled', True)
        else:
            method = methodcaller('setEnabled', False)
        list(map(method, items))  # Runs setEnabled on all of the items

    @pyqtSlot(str)
    def process_hw(self, path):  # path is DROPPED into the table
        self.hw_path = path.strip()  # removes \n etc
        # a little clean up is necessary for the path
        self.hw_path = os.path.normpath(self.hw_path).lstrip("file:")
        if self.is_linux:
            self.hw_path = os.path.join('/', self.hw_path)  # put a / at start
        elif self.is_windows:  # / should be \
            self.hw_path = self.hw_path.replace('/', os.sep).lstrip(os.sep)

        # Update the folder tree table
        self.folder_model.setRootPath(self.hw_path)
        self.folder_tree_view.setRootIndex(self.folder_model.index(self.hw_path))

        self.hw_folders.clear()  # clear previous homework folders(if any)
        self.st_table.clearContents()  # table contents(if any) not col. headers
        self.command = ""  # reset the console output

        if os.path.isfile(path): # TODO: single file HW
            print("Single File is not yet implemented")
        self.compile_box_update(self.hw_path)  # put folder path in terminal
        
        # Retrieve the zip files only and sort them
        files = os.listdir(self.hw_path)
        files = [f for f in files if f.lower().endswith(".zip")]
        files.sort()

        # Setting up the zip thread
        self.zip_thread = ZipHandle(self.hw_path, files, self.hw_re)
        self.zip_thread.log_trigger.connect(self.compile_box_update)
        self.zip_thread.hw_add_trigger.connect(self.table_hw_add)
        self.zip_thread.start()

    @pyqtSlot(int, int)
    def hw_clicked(self, row, _):
        """ A Cell is clicked, row, col is also passed in here """
        if row == self.prev_row:  # if double selecting a row, deselect
            self.st_table.clearSelection()
            self.prev_row = -1
            self.enable_config(False)
            return
        else:
            self.prev_row = row

        # We use this event handler since it does similar thing
        self.closeEvent(None)

        # Retrieve other information of the hw from different columns
        self.sel_cn = self.st_table.item(row, self.st_tab_ind["CN"]).text()
        self.sel_hw_num = self.st_table.item(row, self.st_tab_ind["HW_Num"]).text()
        self.sel_st_num = self.st_table.item(row, self.st_tab_ind["St_Num"]).text()

        # This part updates the folder tree
        self.sel_hw_path = os.path.join(self.hw_path, "{}-HW{}-{}".format(
            self.sel_cn, self.sel_hw_num, self.sel_st_num))
        folder_index = self.folder_model.index(self.sel_hw_path)
        self.folder_tree_view.collapseAll()
        self.folder_tree_view.expand(folder_index)  # triggers expanded

        # Enabling the buttons below terminal
        self.enable_config(True)

    @pyqtSlot()
    def open_code(self):
        """ This event handler is run whenever user clicks open code button"""
        # TODO: Add support for the editor if in other directories
        p = Popen(shlex.split(self.editor + ' "' + self.sel_hw_path + '"'),
                  shell=False, start_new_session=True)  # open code editor
        self._processes.append(p)

    @pyqtSlot()
    def open_report(self):
        row = self.st_table.currentRow()
        sel_rep_name = self.st_table.item(row, self.st_tab_ind["Report"]).text()
        if sel_rep_name == "N/A":
            self.compile_box_update("Can not find report file.")
            return
        sel_report_path = os.path.join(self.sel_hw_path, sel_rep_name)
        pdf_cmd = shlex.split(self.pdf_viewer)
        pdf_cmd.extend([sel_report_path])
        p = Popen(pdf_cmd, shell=False, start_new_session=True)  # open pdf
        self._processes.append(p)

    @pyqtSlot(int)
    def prog_type_changed(self, index):
        self.sel_prog_type = self.prog_type_combo.currentText()
        if self.sel_prog_type != "C++":  # No compilation step except C++
            self.compile_push_button.setVisible(False)
        else:
            self.compile_push_button.setVisible(True)

    @pyqtSlot()
    def compile_hw(self):  # Compile push button is clicked
        """ In this function the selected hw path is compiled. """
        if self.sel_prog_type == "C++":
            self.c_comp.change_root(self.sel_hw_path)
            self.compile_box_update("{}: C++".format(os.path.basename(
                self.sel_hw_path)))
            self.compile_box_update("Generating Makefile if needed ...")
            self.c_comp.generate_makefiles()
            self.compile_box_update("\nCompiling the Questions, Wait ...")
            self.c_comp.compile()  # compiles all the folders with proper C++
        elif self.sel_prog_type == "Matlab":
            pass
        elif self.sel_prog_type == "Python":
            pass

    @pyqtSlot()
    def run_hw(self):
        """ This function is run when user clicks on Run button """
        if self.sel_prog_type == "C++":
            comp = self.c_comp
        elif self.sel_prog_type == "Python": # comp = self.py_comp
            pass
        elif self.sel_prog_type == "Matlab":
            comp = self.mat_compiler
            comp.change_root(self.sel_hw_path)
            script_files = self.mat_compiler.search_scripts()
            if len(script_files) == 0:
                self.compile_box_update("Did not find any script to run.")
                return

        self.compile_box_update("{}: Execute".format(self.sel_prog_type))
        comp.exec()  # execute proper compiler
        self.compile_box_update("{0}\n{0}".format(self.sep))

    @pyqtSlot(QModelIndex)
    def expanded(self, index):  # Tree view is expanded at one of the indexes
        # Disable this line, since it decreases the width, 1 level is only open
        # self.folder_tree_view.resizeColumnToContents(0)
        if index != None:
            self.folder_tree_view.setCurrentIndex(index)
            self.folder_tree_view.scrollTo(index)

    @pyqtSlot(QModelIndex)
    def open_file_folder(self, index):  # double clicked on something
        """ This function can open certian filetypes. A handler needs to open the
            file. For the moment only pdf files are opened."""
        path = self.folder_model.fileInfo(index).absoluteFilePath()
        if os.path.isdir(path): # No need to do anything
            return
        if self.is_linux:
            if path.lower().endswith(".pdf"):
                p = Popen(shlex.split(self.pdf_viewer + "\"" + path + "\""),
                          shell=False, start_new_session=True)
                self._processes.append(p)

    def table_hw_add(self, hw_folder):
        self.hw_folders.append(hw_folder)
        hw_ls = os.listdir(os.path.join(self.hw_path, hw_folder))
        hw_dirs = [item for item in hw_ls if
                   os.path.isdir(os.path.join(self.hw_path, hw_folder, item))]
        hw_files = [item for item in hw_ls if
                   os.path.isfile(os.path.join(self.hw_path, hw_folder, item))]
        course_name, file_name, hw_num, st_num = self.hw_re.match(
            hw_folder).groups()

        cur_row = len(self.hw_folders) - 1
        self.st_table.insertRow(cur_row)
        self.st_table.setItem(cur_row, self.st_tab_ind["CN"],
                              QTableWidgetItem(course_name))  # hw_num
        self.st_table.item(cur_row, self.st_tab_ind["CN"]).\
            setTextAlignment(QtCore.Qt.AlignCenter)
        self.st_table.setItem(cur_row, self.st_tab_ind["HW_Num"],
                              QTableWidgetItem(hw_num))  # hw_num
        self.st_table.item(cur_row, self.st_tab_ind["HW_Num"]).\
            setTextAlignment(QtCore.Qt.AlignCenter)
        self.st_table.setItem(cur_row, self.st_tab_ind["St_Num"],
                              QTableWidgetItem(st_num))  # st_num
        self.st_table.item(cur_row, self.st_tab_ind["St_Num"]). \
            setTextAlignment(QtCore.Qt.AlignCenter)
        st_name_item = QTableWidgetItem("وارد نشده است")
        st_name_item.setFont(self.persian_font)
        self.st_table.setItem(cur_row, self.st_tab_ind["St_Name"], st_name_item)
        self.st_table.item(cur_row, self.st_tab_ind["St_Name"]). \
            setTextAlignment(QtCore.Qt.AlignHCenter)

        # ignore chars from the homework folder names in the table,
        # e.g.: Q1, Q2 -> 1, 2
        if len(hw_dirs) > 0:
            hw_dirs_str = ' '.join(hw_dirs)
            hw_dirs_str = [c for c in hw_dirs_str if not c.isalpha()]
            hw_dirs_str.sort()
            hw_dirs_str = ' '.join(hw_dirs_str)  # convert back to str
        else:
            hw_dirs_str = "N/A"
        self.st_table.setItem(cur_row, self.st_tab_ind["Folders"],
                              QTableWidgetItem(hw_dirs_str)) # hw folders

        # Finding the report file name and store in report_file variable
        if len(hw_files) > 0:
            # filter out non pdf files
            hw_files = [f for f in hw_files if f.lower().endswith(".pdf")]
            if len(hw_files) > 1:
                self.compile_box_update("{}: multiple PDFs".format(hw_folder))
            if len(hw_files) > 0:  # can be greater than 1, only output one
                report_file = hw_files[0]
            else:
                report_file = "N/A"
        else:   # No report file available
            report_file = "N/A"
        self.st_table.setItem(cur_row, self.st_tab_ind["Report"],
                              QTableWidgetItem(report_file))
        #QApplication.instance().processEvents()

    def compile_box_update(self, text):
        if text == "":  # Ignore input
            return
        self.command += text + "\n"
        self.compile_box.setText(self.command)
        self.compile_box.moveCursor(PyQt5.QtGui.QTextCursor.End)
        QApplication.instance().processEvents()

    # This is called wihen the dialog is closed by pressing x
    def closeEvent(self, event):
        self.c_comp.kill_windows()
        self.mat_compiler.kill_windows()
        if self.is_linux:
            for p in self._processes:
                os.killpg(os.getpgid(p.pid), signal.SIGTERM)
            self._processes.clear()
        elif self.is_windows: # TODO: Add support for windows
            pass
        # TODO: delete folders created in the program, only keep zip files



app = QApplication(sys.argv)
window = MyWindow()
window.show()
sys.exit(app.exec_())
