"""
anki-addon: open field contents in WYSIWYG-Editor(like TinyMCE)

Copyright (c) 2019 ignd
          (c) 2014 - 2016 Detlev Offenbach <detlev@die-offenbachs.de>
              (the function __execJavaScript)
          (c) Ankitects Pty Ltd and contributors
          (c) 2018 Hyun Woo Park (cloze functions in template file)

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as
published by the Free Software Foundation, either version 3 of the
License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.


This add-on bundles TinyMCE downloaded from http://download.tiny.cloud/tinymce/community/tinymce_4.9.4.zip
This site states "TinyMCE is open source and licensed under LGPL 2.1.", see web/tinymce/js/tinymce/license.txt
The tinymce package does not contain any information on the copyright.
TinyMCE is developed at https://github.com/tinymce/tinymce
For years there's been a CLA at https://github.com/tinymce/tinymce/blob/master/modules/tinymce/readme.md
that states that each contributor agress that the copyright is changed to Ephox Corporation.
So likely tinymce is: copyright (c) Ephox Corporation.
"""

import os
import io
import time

from anki.hooks import addHook

import aqt
from aqt import mw
from aqt.qt import *
from aqt.utils import showInfo, askUser
from aqt.editor import Editor
from aqt.webview import AnkiWebView


def gc(arg, fail=False):
    return mw.addonManager.getConfig(__name__).get(arg, fail)


addon_path = os.path.dirname(__file__)
addonfoldername = os.path.basename(addon_path)
regex = r"(web.*)"
mw.addonManager.setWebExports(__name__, regex)
web_path = "/_addons/%s/web/" % addonfoldername


addon_cssfiles = ["webview_override.css",
                  ]
other_cssfiles = []
cssfiles = addon_cssfiles + other_cssfiles

addon_jsfiles = ["tinymce4/js/tinymce/tinymce.min.js",
                 ]
other_jsfiles = ["jquery.js",
                 ]
jsfiles = addon_jsfiles + other_jsfiles


class MyWebView(AnkiWebView):

    # via https://riverbankcomputing.com/pipermail/pyqt/2016-May/037449.html
    # https://github.com/pycom/EricShort/blob/master/UI/Previewers/PreviewerHTML.py
    def sync_execJavaScript(self, script):
        """
        Private function to execute a JavaScript function Synchroneously.
        @param script JavaScript script source to be executed
        @type str
        @return result of the script
        @rtype depending upon script result
        """
        from PyQt5.QtCore import QEventLoop
        loop = QEventLoop()
        resultDict = {"res": None}

        def resultCallback(res, resDict=resultDict):
            if loop and loop.isRunning():
                resDict["res"] = res
                loop.quit()

        self.page().runJavaScript(
            script, resultCallback)
        loop.exec_()
        return resultDict["res"]


    def bundledScript(self, fname):
        if fname in addon_jsfiles:
            return '<script src="%s"></script>' % (web_path + fname)
        else:
            return '<script src="%s"></script>' % self.webBundlePath(fname)

    def bundledCSS(self, fname):
        if fname in addon_cssfiles:
            return '<link rel="stylesheet" type="text/css" href="%s">' % (web_path + fname)
        else:
            return '<link rel="stylesheet" type="text/css" href="%s">' % self.webBundlePath(fname)


class MyDialog(QDialog):
    def __init__(self, parent, bodyhtml):
        super(MyDialog, self).__init__(parent)

        self.jsSavecommand = "tinyMCE.activeEditor.getContent();"
        self.setWindowTitle('Anki - edit current field in TinyMCE4')
        self.resize(gc("default_width", 810), gc("default_height", 1100))

        mainLayout = QVBoxLayout()
        mainLayout.setContentsMargins(0, 0, 0, 0)
        mainLayout.setSpacing(0)
        self.setLayout(mainLayout)
        self.web = MyWebView(self)
        self.web.allowDrops = False   # default in webview/AnkiWebView is False
        self.web.title = "tinymce4"
        self.web.contextMenuEvent = self.contextMenuEvent
        mainLayout.addWidget(self.web)

        self.buttonBox = QDialogButtonBox(self)
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Cancel | QDialogButtonBox.Save)
        mainLayout.addWidget(self.buttonBox)

        self.buttonBox.accepted.connect(self.onAccept)
        self.buttonBox.rejected.connect(self.onReject)
        QMetaObject.connectSlotsByName(self)
        acceptShortcut = QShortcut(QKeySequence("Ctrl+Return"), self)
        acceptShortcut.activated.connect(self.onAccept)

        self.web.stdHtml(bodyhtml, cssfiles, jsfiles)

    def onAccept(self):
        global editedfieldcontent
        editedfieldcontent = self.web.sync_execJavaScript(self.jsSavecommand)
        self.web = None  # doesn't remove?
        # self.web._page.windowCloseRequested()  # native qt signal not callable
        # self.web._page.windowCloseRequested.connect(self.web._page.window_close_requested)
        self.accept()
        # self.done(0)

    def onReject(self):
        ok = askUser("Close and lose current input?")
        if ok:
            self.reject()

    def closeEvent(self, event):
        ok = askUser("Close and lose current input?")
        if ok:
            event.accept()
        else:
            event.ignore()


def _onWYSIWYGUpdateField(self):
    try:
        note = mw.col.getNote(self.nid)
    except:   # new note
        self.note.fields[self.myfield] = editedfieldcontent
        self.note.flush()
    else:
        note.fields[self.myfield] = editedfieldcontent
        note.flush()
        mw.requireReset()
        mw.reset()
    self.loadNote(focusTo=self.myfield)
Editor._onWYSIWYGUpdateField = _onWYSIWYGUpdateField


def on_WYSIWYGdialog_finished(self, status):
    if status:
        self.saveNow(lambda: self._onWYSIWYGUpdateField())
Editor.on_WYSIWYGdialog_finished = on_WYSIWYGdialog_finished


def wysiwyg_dialog(self, field):
    bodyhtml = templatecontent % (
        gc('fontSize'),
        gc('font'),
        self.note.fields[field]
        )
    d = MyDialog(None, bodyhtml)
    # exec_() doesn't work, see  https://stackoverflow.com/questions/39638749/
    d.finished.connect(self.on_WYSIWYGdialog_finished)
    d.setModal(True)
    d.show()
    d.web.setFocus()
Editor.wysiwyg_dialog = wysiwyg_dialog


def open_in_add_window(val):
    newNote = mw.col.newNote()
    newNote.fields[ceA['toAddWindow']['fdx']] = val
    tags = ceA['toAddWindow']['tags']
    newNote.tags = [t for t in tags.split(" ") if t]
    deckname = ceA['toAddWindow']['deck']
    modelname = ceA['toAddWindow']['notetype']

    addCards = aqt.dialogs.open('AddCards', mw.window())
    addCards.editor.setNote(newNote, focusTo=0)
    addCards.deckChooser.setDeckName(deckname)
    addCards.modelChooser.models.setText(modelname)
    addCards.activateWindow()


def direct_create_new_note(val):
    c = ceA['createNewNote']  # createNewNote toAddWindow
    newNote = mw.col.newNote()
    newNote.mid = c['mid']    # model id
    tags = c['tags']
    newNote.tags = [t for t in tags.split(" ") if t]   # see tags.py
    newNote.fields[c['fdx']] = val
    newNote.flush()
    mw.col.addNote(newNote)
# nid = newNote.id   #reinsert new nid as a reference?


def readfile():
    addondir = os.path.join(os.path.dirname(__file__))
    filefullpath = os.path.join(addondir, "template_tiny4_body.html")
    with io.open(filefullpath, 'r', encoding='utf-8') as f:
        return f.read()
templatecontent = readfile()


def tiny4_start(self):
    self.myfield = self.currentField
    self.saveNow(lambda: self.wysiwyg_dialog(self.myfield))


def keystr(k):
    key = QKeySequence(k)
    return key.toString(QKeySequence.NativeText)


def setupEditorButtonsFilter(buttons, editor):
    if gc('tinymce4Hotkey'):
        b = editor.addButton(
            icon=None,  # os.path.join(addon_path, "icons", "tm.png"),
            cmd="T4",
            func=tiny4_start,
            tip="edit current field in external window ({})".format(keystr(gc('tinymce4Hotkey'))),
            keys=gc('tinymce4Hotkey'))
        buttons.append(b)
    return buttons
addHook("setupEditorButtons", setupEditorButtonsFilter)