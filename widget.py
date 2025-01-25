# split_binary_file.py (UI Code)
import os
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                                QLabel, QLineEdit, QPushButton, QFileDialog,
                                QProgressBar, QCheckBox, QMessageBox)
from PySide6.QtCore import Slot, QThread, Signal
from binary_splitter_core import split_binary_file, load_config_defaults, detect_frame_size

# --- Worker Thread Class (Split Only) ---
class FileSplitterWorker(QThread):
    progress_signal = Signal(int)
    finished_signal = Signal(str)
    error_signal = Signal(str)
    stop_signal = Signal()
    frame_size_detected_signal = Signal(int) # New signal to emit detected frame size

    def __init__(self, input_file_path, bulk_size_gb, frame_size_bytes, output_prefix, auto_detect_frame_size, sync_word_hex):
        super().__init__()
        self.input_file_path = input_file_path
        self.bulk_size_gb = bulk_size_gb
        self.frame_size_bytes = frame_size_bytes
        self.output_prefix = output_prefix
        self.auto_detect_frame_size = auto_detect_frame_size
        self.sync_word_hex = sync_word_hex
        self._is_stopped = False

    def run(self):
        try:
            if self.auto_detect_frame_size:
                detected_frame_size = detect_frame_size(self.input_file_path, self.sync_word_hex)
                if detected_frame_size:
                    frame_size_to_use = detected_frame_size
                    self.frame_size_detected_signal.emit(frame_size_to_use) # Emit detected frame size
                else:
                    raise ValueError("Frame size auto-detection failed.")
            else:
                frame_size_to_use = self.frame_size_bytes

            split_binary_file(
                self.input_file_path,
                self.bulk_size_gb,
                frame_size_to_use,
                self.output_prefix,
                progress_callback=self.progress_signal.emit,
                stop_flag=lambda: self._is_stopped
            )
            self.finished_signal.emit("File splitting complete.")
        except Exception as e:
            self.error_signal.emit(str(e))
        finally:
            pass

    def stop_operation(self):
        self._is_stopped = True
        self.stop_signal.emit()
        self.quit()
        self.wait()


# --- UI Class (Split Only) ---
class FileSplitterUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Binary File Splitter")

        # Load defaults from config.json
        defaults = load_config_defaults()
        default_frame_size = defaults["default_frame_size_bytes"]
        default_bulk_size_gb = defaults["default_bulk_size_gb"]
        default_sync_word_hex = defaults["default_sync_word_hex"]

        # UI Elements
        self.file_path_label = QLabel("Input File:")
        self.file_path_edit = QLineEdit()
        self.browse_button = QPushButton("Browse")
        self.browse_button.clicked.connect(self.browse_file)

        self.frame_size_label = QLabel("Frame Size (bytes):")
        self.frame_size_edit = QLineEdit()
        self.frame_size_edit.setText(str(default_frame_size))

        self.bulk_size_label = QLabel("Bulk Size (GB):")
        self.bulk_size_edit = QLineEdit()
        self.bulk_size_edit.setText(str(default_bulk_size_gb))

        self.output_prefix_label = QLabel("Output Prefix (optional):")
        self.output_prefix_edit = QLineEdit()
        self.output_prefix_edit.setPlaceholderText("Default: Input filename")

        self.auto_detect_frame_size_checkbox = QCheckBox("Auto-detect Frame Size")
        self.auto_detect_frame_size_checkbox.stateChanged.connect(self.toggle_frame_size_edit)

        self.sync_word_label = QLabel("Sync Word (Hex):")
        self.sync_word_edit = QLineEdit()
        self.sync_word_edit.setText(default_sync_word_hex)
        self.sync_word_edit.setEnabled(False)

        self.split_button = QPushButton("Split File")
        self.split_button.clicked.connect(self.start_split_operation)

        self.stop_button = QPushButton("Stop")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_current_operation)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)

        self.status_label = QLabel("")

        # Layouts (same as before)
        file_layout = QHBoxLayout()
        file_layout.addWidget(self.file_path_label)
        file_layout.addWidget(self.file_path_edit)
        file_layout.addWidget(self.browse_button)

        frame_size_layout = QHBoxLayout()
        frame_size_layout.addWidget(self.frame_size_label)
        frame_size_layout.addWidget(self.frame_size_edit)
        frame_size_layout.addWidget(self.auto_detect_frame_size_checkbox)

        sync_word_layout = QHBoxLayout()
        sync_word_layout.addWidget(self.sync_word_label)
        sync_word_layout.addWidget(self.sync_word_edit)

        prefix_layout = QHBoxLayout()
        prefix_layout.addWidget(self.output_prefix_label)
        prefix_layout.addWidget(self.output_prefix_edit)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.split_button)
        button_layout.addWidget(self.stop_button)

        main_layout = QVBoxLayout()
        main_layout.addLayout(file_layout)
        main_layout.addLayout(frame_size_layout)
        main_layout.addLayout(sync_word_layout)
        main_layout.addWidget(self.bulk_size_label)
        main_layout.addWidget(self.bulk_size_edit)
        main_layout.addLayout(prefix_layout)
        main_layout.addLayout(button_layout)
        main_layout.addWidget(self.progress_bar)
        main_layout.addWidget(self.status_label)

        self.setLayout(main_layout)
        self.worker_thread = None


    @Slot()
    def browse_file(self):
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(self, "Select Binary File")
        if file_path:
            self.file_path_edit.setText(file_path)

    @Slot(int)
    def toggle_frame_size_edit(self, state):
        is_auto_detect_enabled = (state == 2)
        self.frame_size_edit.setEnabled(not is_auto_detect_enabled)
        self.sync_word_edit.setEnabled(is_auto_detect_enabled)


    @Slot()
    def start_split_operation(self):
        input_file = self.file_path_edit.text()
        output_prefix_input = self.output_prefix_edit.text()
        output_prefix = output_prefix_input if output_prefix_input else "output_bulk"
        auto_detect_frame_size = self.auto_detect_frame_size_checkbox.isChecked()
        sync_word_hex = self.sync_word_edit.text()

        try:
            bulk_size_gb = float(self.bulk_size_edit.text())
            if not auto_detect_frame_size:
                frame_size_bytes = int(self.frame_size_edit.text())
            else:
                frame_size_bytes = 0

            if not os.path.exists(input_file):
                raise FileNotFoundError(f"Input file not found: {input_file}")

            if auto_detect_frame_size and not sync_word_hex:
                raise ValueError("Sync word (Hex) is required for auto-detection.")


            self.status_label.setText("Splitting in progress...")
            self.progress_bar.setValue(0)
            self.split_button.setEnabled(False)
            self.stop_button.setEnabled(True)

            self.worker_thread = FileSplitterWorker(input_file, bulk_size_gb, frame_size_bytes, output_prefix, auto_detect_frame_size, sync_word_hex)
            self.worker_thread.progress_signal.connect(self.update_progress)
            self.worker_thread.finished_signal.connect(self.operation_finished)
            self.worker_thread.error_signal.connect(self.operation_error)
            self.worker_thread.frame_size_detected_signal.connect(self.update_frame_size_field) # Connect new signal
            self.worker_thread.start()


        except ValueError as e:
            QMessageBox.warning(self, "Input Error", str(e))
            self.status_label.setText(f"Error: {e}")
        except FileNotFoundError as e:
            self.status_label.setText(f"Error: {e}")
        except Exception as e:
            self.status_label.setText(f"Error starting split: {e}")


    @Slot()
    def stop_current_operation(self):
        if self.worker_thread and self.worker_thread.isRunning():
            self.status_label.setText("Stopping operation...")
            self.stop_button.setEnabled(False)
            self.worker_thread.stop_operation()


    @Slot(int)
    def update_progress(self, progress):
        self.progress_bar.setValue(progress)

    @Slot(str)
    def operation_finished(self, message):
        self.status_label.setText(message)
        self.split_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.worker_thread = None

    @Slot(str)
    def operation_error(self, error_message):
        QMessageBox.critical(self, "Error", f"An error occurred: {error_message}")
        self.status_label.setText(f"Error: {error_message}")
        self.progress_bar.setValue(0)
        self.split_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.worker_thread = None

    @Slot(int) # New slot to update frame size field
    def update_frame_size_field(self, frame_size):
        self.frame_size_edit.setText(str(frame_size))
        self.status_label.setText(f"Auto-detected frame size: {frame_size} bytes. Splitting in progress...") # Update status label


if __name__ == '__main__':
    app = QApplication([])
    window = FileSplitterUI()
    window.show()
    app.exec()
