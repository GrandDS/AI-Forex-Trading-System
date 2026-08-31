from PyQt5 import QtWidgets, QtCore
from config import BotConfig
from trader import DayTradingBot


class BotWorker(QtCore.QThread):
    log_signal = QtCore.pyqtSignal(str)

    def __init__(self, cfg: BotConfig):
        super().__init__()
        self.cfg = cfg
        self.bot = DayTradingBot(cfg, self._log)

    def _log(self, msg: str):
        self.log_signal.emit(msg)

    def run(self):
        self.bot.run_forever()

    def stop(self):
        self.bot.stop()


class MainWindow(QtWidgets.QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("OANDA DayBot (M5 Intelligent)")
        self.resize(1000, 700)

        self.worker = None

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)

        layout = QtWidgets.QVBoxLayout(central)

        form = QtWidgets.QFormLayout()
        layout.addLayout(form)

        # --- Trade events label ---
        self.trade_events_label = QtWidgets.QLabel("Trade Events: none yet")
        self.trade_events_label.setStyleSheet(
            "font-size:14px;font-weight:bold;padding:6px;border:1px solid #ccc;border-radius:6px;"
        )
        layout.addWidget(self.trade_events_label)

        # --- Environment ---
        self.env = QtWidgets.QComboBox()
        self.env.addItems(["practice", "live"])
        form.addRow("Environment", self.env)

        # --- API token ---
        self.token = QtWidgets.QLineEdit()
        self.token.setEchoMode(QtWidgets.QLineEdit.Password)
        form.addRow("API Token", self.token)

        # --- Account ID ---
        self.account = QtWidgets.QLineEdit()
        form.addRow("Account ID", self.account)

        # --- Instrument ---
        self.instrument = QtWidgets.QLineEdit("EUR_USD")
        form.addRow("Instrument", self.instrument)

        # --- Granularity ---
        self.granularity = QtWidgets.QComboBox()
        self.granularity.addItems(["M5", "M15", "M1"])
        self.granularity.setCurrentText("M5")
        form.addRow("Granularity", self.granularity)

        # --- Fixed Units ---
        self.fixed_units = QtWidgets.QSpinBox()
        self.fixed_units.setRange(1, 1000000)
        self.fixed_units.setValue(1000)
        form.addRow("Fixed Units", self.fixed_units)

        # --- Strategy toggles ---
        self.enable_breakout = QtWidgets.QCheckBox("Enable Breakout")
        self.enable_breakout.setChecked(True)
        form.addRow(self.enable_breakout)

        self.enable_pullback = QtWidgets.QCheckBox("Enable Pullback")
        self.enable_pullback.setChecked(True)
        form.addRow(self.enable_pullback)

        self.enable_vwap = QtWidgets.QCheckBox("Enable VWAP Mean Reversion")
        self.enable_vwap.setChecked(True)
        form.addRow(self.enable_vwap)

        # --- Buttons ---
        btn_row = QtWidgets.QHBoxLayout()
        layout.addLayout(btn_row)

        self.start_btn = QtWidgets.QPushButton("Start Bot")
        self.stop_btn = QtWidgets.QPushButton("Stop Bot")
        self.save_log_btn = QtWidgets.QPushButton("Save Log")

        self.stop_btn.setEnabled(False)

        btn_row.addWidget(self.start_btn)
        btn_row.addWidget(self.stop_btn)
        btn_row.addWidget(self.save_log_btn)

        # --- Log panel ---
        self.log = QtWidgets.QPlainTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log)

        # --- Button connections ---
        self.start_btn.clicked.connect(self.start_bot)
        self.stop_btn.clicked.connect(self.stop_bot)
        self.save_log_btn.clicked.connect(self.save_log)

    # -------------------------------------

    def append_log(self, msg: str):

        self.log.appendPlainText(msg)

        # Update trade events label if important
        key_phrases = [
            "Started a trade",
            "Closed trade",
            "Partial close"
        ]

        if any(k in msg for k in key_phrases):
            self.trade_events_label.setText(f"Trade Events: {msg}")

    # -------------------------------------

    def start_bot(self):

        cfg = BotConfig(
            api_token=self.token.text().strip(),
            account_id=self.account.text().strip(),
            environment=self.env.currentText(),
            instrument=self.instrument.text().strip().replace("/", "_").upper(),
            granularity=self.granularity.currentText(),
            use_fixed_units=True,
            fixed_units=int(self.fixed_units.value()),
            enable_breakout=self.enable_breakout.isChecked(),
            enable_pullback=self.enable_pullback.isChecked(),
            enable_vwap_mr=self.enable_vwap.isChecked(),
        )

        if not cfg.api_token or not cfg.account_id:
            self.append_log("Please enter API Token and Account ID.")
            return

        self.worker = BotWorker(cfg)
        self.worker.log_signal.connect(self.append_log)
        self.worker.start()

        self.append_log("Starting bot...")

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

    # -------------------------------------

    def stop_bot(self):

        if self.worker:

            self.append_log("Stopping bot...")

            self.worker.stop()
            self.worker.wait(5000)

            self.worker = None

        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

        self.append_log("Bot stopped.")

    # -------------------------------------

    def save_log(self):

        from datetime import datetime

        text = self.log.toPlainText().strip()

        if not text:
            self.append_log("Log is empty — nothing to save.")
            return

        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        default_name = f"daybot_log_{ts}.txt"

        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save Bot Log",
            default_name,
            "Text Files (*.txt);;All Files (*)"
        )

        if not path:
            self.append_log("Save cancelled.")
            return

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)

            self.append_log(f"Log saved to {path}")

        except Exception as e:
            self.append_log(f"Error saving log: {e}")


# -------------------------------------


def run_app():

    app = QtWidgets.QApplication([])

    window = MainWindow()
    window.show()

    app.exec_()