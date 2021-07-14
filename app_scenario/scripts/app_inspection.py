#!/usr/bin/python
# -*- coding: utf8 -*-#

import os
import signal
import traceback
import time
import datetime
import dateutil.parser
import urllib

class MyLoop(Loop):
    def on_create(self, event):
        return ResponseInfo()

    def on_resume(self, event):
        return ResponseInfo()

    def on_loop(self):
        return ResponseInfo()

    def on_pause(self, event):
        return ResponseInfo()

    def on_destroy(self, event):
        return ResponseInfo()

__class = MyLoop
DOCUMENT_DIR = os.path.expanduser("~") + "/document/"

if __name__ == "__main__":
    signal.signal(signal.SIGINT, exit)
    try:
        wrapper = RosWrapper(
            __class,
            manifest_path=os.path.join(os.path.dirname(__file__), "app_inspection.yaml"),
        )
    except:
        traceback.self.logger.info_exc()