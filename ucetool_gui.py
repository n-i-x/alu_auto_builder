#!/usr/bin/env python3

import os
import sys
import functools
from pathlib import Path
import logging

from PyQt5.QtCore import QDir, pyqtRemoveInputHook
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QLabel, \
    QPushButton, QWidget, QFileDialog, QComboBox, QDialog, QCheckBox, QMessageBox

from shared import common_utils, error_messages
import operations


def get_combo_opt_type(name):
    name_parts = name.split('_')
    try:
        suffix = name_parts[-1]
        if suffix in ('dir', 'path'):
            return suffix
    except IndexError:
        pass
    return 'text'


def title_from_name(name):
    return name.replace('_', ' ').title()


class MainWindow(QMainWindow):

    def __init__(self, operations, parent=None):
        super().__init__(parent)
        self.setWindowTitle('UCE Tool')
        self.main_layout = self._create_main_layout()
        self.op_buttons = {}
        self._create_operation_buttons(operations)
        self.exit_button = QPushButton('Exit')
        self.main_layout.addWidget(self.exit_button)

    def _create_main_layout(self):
        main_layout = QVBoxLayout()
        layout_container = QWidget()
        layout_container.setLayout(main_layout)
        self.setCentralWidget(layout_container)
        return main_layout

    def _create_operation_buttons(self, operations):
        for operation_name, operation_spec in operations.items():
            self._create_button(operation_name, operation_spec)

    def _create_button(self, operation_name, operation_spec):
        button = QPushButton(title_from_name(operation_name))
        button.setToolTip(operation_spec['help'])
        self.op_buttons[operation_name] = button
        self.main_layout.addWidget(button)


class OperationDialog(QDialog):

    def __init__(self, name, opts, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title_from_name(name))
        self.dialog_layout = QVBoxLayout()
        self.check_boxes = {}
        self.combo_selects = {}
        self.select_buttons = {}
        self._create_opt_inputs(opts)
        self.ok_button = QPushButton('OK')
        self.close_button = QPushButton('Close')
        self.help_button = QPushButton('Help')
        self._create_user_input_widget(self.ok_button, self.close_button, self.help_button)
        self.setLayout(self.dialog_layout)

    def _create_user_input_widget(self, *args):
        layout = QHBoxLayout()
        widget = QWidget()
        widget.setLayout(layout)
        for arg in args:
            layout.addWidget(arg)
        self.dialog_layout.addWidget(widget)

    def _create_opt_inputs(self, opts):
        for opt in opts:
            if opt['short'].isupper():
                self._create_checkbox_widget(opt)
            else:
                self._create_select_widget(opt)

    def _create_title_label(self, opt):
        title_label = QLabel()
        title_label.setToolTip(opt['help'])
        title_label.setFixedWidth(100)
        title_label.setText(title_from_name(opt['name']))
        return title_label

    def _create_select_button(self, opt):
        button = QPushButton('Select')
        button.setFixedHeight(30)
        self.select_buttons[opt['name']] = button
        return button

    def _create_checkbox_widget(self, opt):
        widgets = [self._create_title_label(opt)]
        checkbox = QCheckBox()
        self.check_boxes[opt['name']] = checkbox
        widgets.append(checkbox)
        self._create_user_input_widget(*widgets)

    def _create_select_widget(self, opt):
        widgets = [self._create_title_label(opt)]
        combo = QComboBox()
        combo.addItems(opt.get('selections', []))
        combo.setFixedWidth(200)
        combo.setEditable(True)
        self.combo_selects[opt['name']] = combo
        widgets.append(combo)
        if get_combo_opt_type(opt['name']) in ('dir', 'path'):
            widgets.append(self._create_select_button(opt))
        self._create_user_input_widget(*widgets)


class Controller:

    def __init__(self, operations):
        self.dialog_dir = str(Path.home())
        self.current_view = None
        self.args = {}
        self.operations = operations
        self.current_operation_name = None

    def _close_current_view(self):
        if self.current_view:
            self.current_view.close()

    def _show_view(self, view):
        self.current_view = view
        view.show()

    def _connect_dialog_signals(self, view):
        for name, button in view.select_buttons.items():
            if get_combo_opt_type(name) == 'dir':
                button.clicked.connect(functools.partial(self._choose_dir, view, name))
            elif get_combo_opt_type(name) == 'path':
                button.clicked.connect(functools.partial(self._choose_file, view, name))
        view.ok_button.clicked.connect(self._run)
        view.close_button.clicked.connect(self.show_main_window)
        view.help_button.clicked.connect(self._show_help_dialog)
        for name, combo in view.combo_selects.items():
            combo.currentTextChanged.connect(functools.partial(self._change_combo_content, view, name))
            combo.currentIndexChanged.connect(functools.partial(self._change_combo_content, view, name))
        for name, checkbox in view.check_boxes.items():
            checkbox.toggled.connect(functools.partial(self._change_checkbox_value, view, name))

    def _show_help_dialog(self):
        dialog = QMessageBox()
        dialog.setWindowTitle('{0}: Help'.format(title_from_name(self.current_operation_name)))
        html_source = os.path.join(common_utils.get_app_root(), 'html', '{0}.html'.format(self.current_operation_name))
        dialog.setText(common_utils.get_file_content(html_source, 'r'))
        dialog.setStandardButtons(QMessageBox.Close)
        dialog.exec_()

    def _show_dialog(self, name):
        self.args = {}
        self._close_current_view()
        self.current_operation_name = name
        view = OperationDialog(name, operations.operations[name]['options'])
        self._connect_dialog_signals(view)
        self._show_view(view)

    def show_main_window(self):
        self._close_current_view()
        view = MainWindow(self.operations)
        for name, button in view.op_buttons.items():
            button.clicked.connect(functools.partial(self._show_dialog, name))
        view.exit_button.clicked.connect(sys.exit)
        self._show_view(view)

    # TODO - choose dir in combo box if valid
    def _choose_dir(self, view, name):
        dir_name = QFileDialog.getExistingDirectory(view, 'Select Directory', self.dialog_dir)
        if dir_name:
            dir_name = QDir.toNativeSeparators(dir_name)
        if os.path.isdir(dir_name):
            view.combo_selects[name].setCurrentText(dir_name)
            self.dialog_dir = dir_name

    # TODO - Neaten this up. It's a last-minute fudge to choose between saving/opening. Re-add isfile() for open
    def _choose_file(self, view, name):
        fd = QFileDialog.getOpenFileName if name in ('input_path', 'core_path') else QFileDialog.getSaveFileName
        file_name = fd(view, 'Select File', self.dialog_dir)[0]
        if file_name:
            file_name = QDir.toNativeSeparators(file_name)
            view.combo_selects[name].setCurrentText(file_name)
            self.dialog_dir = os.path.split(file_name)[0]

    def _change_combo_content(self, view, name):
        self.args[name] = view.combo_selects[name].currentText()

    def _change_checkbox_value(self, view, name):
        self.args[name] = view.check_boxes[name].isChecked()

    def _validate_args(self):
        valid = True
        for option in self.operations[self.current_operation_name]['options']:
            if option['gui_required']:
                if option['name'] not in self.args:
                    logging.error(error_messages.required_option_not_set(option['name']))
                    valid = False
            else:
                if option['name'] not in self.args:
                    self.args[option['name']] = None
        return valid

    def _run(self):
        if not self._validate_args():
            return False
        self.operations[self.current_operation_name]['runner'](self.args)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format="%(levelname)s : %(message)s")
    pyqtRemoveInputHook()
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(os.path.join(common_utils.get_app_root(), 'data', 'title.png')))
    controller = Controller(operations.operations)
    controller.show_main_window()
    sys.exit(app.exec_())
