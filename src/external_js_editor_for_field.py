"""
anki-addon: open field contents in WYSIWYG-Editor (like TinyMCE)

Copyright (c) 2019- ignd
          (c) Ankitects Pty Ltd and contributors
          (c) 2018 Hyun Woo Park
                   (the cloze functions in template file are taken from
                   https://github.com/phu54321/kian which is AGPLv3) 


This add-on is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as
published by the Free Software Foundation, either version 3 of the
License, or (at your option) any later version.

This add-on is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this add-on.  If not, see <https://www.gnu.org/licenses/>.



This add-on bundles "TinyMCE" in the folder web/tinymce
    Copyright (c) Tiny Technologies, Inc.
    "TinyMCE" was downloaded from http://download.tiny.cloud/tinymce/community/tinymce_4.9.8.zip
    "TinyMCE" contains web/tinymce5/js/tinymce/license.txt
    "TinyMCE" is licensed as LPGL 2.1 (or later)


This add-on bundles the file "sync_execJavaScript.py" which has this copyright and permission
notice: 
    Copyright: 2014 - 2016 Detlev Offenbach <detlev@die-offenbachs.de>
                  (taken from https://github.com/pycom/EricShort/blob/master/UI/Previewers/PreviewerHTML.py)
    License: GPLv3 or later, https://github.com/pycom/EricShort/blob/025a9933bdbe92f6ff1c30805077c59774fa64ab/LICENSE.GPL3


This add-on bundles "ckEditor4" (version 4.3.4) in the folder web/ckeditor4
    Copyright (c) 2003-2014, CKSource - Frederico Knabben. All rights reserved.
    Licensed under the terms of any of the following licenses at your choice:
    GNU General Public License Version 2 or later (the "GPL"), http://www.gnu.org/licenses/gpl.html
    for details see web/ckeditor4/LICENSE.md


This add-on bundles the ckeditor theme "moono-dark" in  web/ckeditor4/skins/moono-dark/
    downloaded form https://ckeditor.com/cke4/addon/moono-dark
    Copyright and License are the same as ckedtior4 according to web/ckeditor4/skins/moono-dark/readme.md


This add-on bundles jquery3.5.1 in the folder web/ckeditor4
    Copyright: JS Foundation and other contributors 
    License: jquery.org/license (MIT)
"""

import os
import io
import time

from anki.hooks import addHook
from anki.utils import isLin

import aqt
from aqt import mw
from aqt.qt import (
    QDialog,
    QVBoxLayout,
    QDialogButtonBox,
    Qt,
    QMetaObject,
    QShortcut,
    QKeySequence,
    QNativeGestureEvent,
    QEvent,
)
from aqt.theme import theme_manager
from aqt.utils import (
     askUser,
     saveGeom,
     restoreGeom,
     showInfo,
     tooltip,
)
from aqt.webview import AnkiWebView, QWebEngineView

from .config import gc
from .sync_execJavaScript import sync_execJavaScript



"""
tinymce5 full screen resizing didn't work in 2020-05: so I added resize_tiny_mce as a workaround

Background:
- what worked in tinymce4 no longer works
- height : "100vh" didn't help though it should? https://www.tiny.cloud/docs/configure/editor-appearance/#height
- nothing else useful in https://www.tiny.cloud/docs/configure/editor-appearance
- autoresize plugin: no help
- github issues search for:   is:issue full screen  label:5.x 

to make sure it's not some interaction with my full config I tested with this minimal config
which made no difference:

<script src="qrc:///qtwebchannel/qwebchannel.js"></script>
<script>   
tinymce.init({
    selector: '.tinymce5_wysiwyg',
    plugins: [
        'fullscreen',       // maximize tinymce to window https://www.tiny.cloud/docs/plugins/fullscreen/
        ],
    setup: function(editor) {
        editor.on('init', function() {
            editor.execCommand('mceFullScreen');   //maximize,  https://stackoverflow.com/a/22959296
        });
    }
})
</script>
<div class="tinymce5_wysiwyg" id="tinymce5_wysiwyg_unique" style="height:100vh;">%(CONTENT)s</div>



or this minimal example:
<script>
tinymce.init({
    selector: 'textarea#basic-example',
    height: 500,
    menubar: false,
    plugins: [
    'fullscreen',
    ],
    menubar: 'file edit view insert format tools table help',
});
</script>
<textarea id="basic-example">%(CONTENT)s</textarea>
"""


addon_path = os.path.dirname(__file__)
addonfoldername = os.path.basename(addon_path)
regex = r"(web[/\\].*)"
mw.addonManager.setWebExports(__name__, regex)
web_path = "/_addons/%s/web/" % addonfoldername


addon_cssfiles = ["webview_override.css",
                  ]
other_cssfiles = []
cssfiles = addon_cssfiles + other_cssfiles


addon_jsfiles = ["tinymce5/js/tinymce/tinymce.min.js",
                 "ckeditor4/ckeditor.js",
                 ]
other_jsfiles = ["jquery.js",
                 ]
jsfiles = addon_jsfiles + other_jsfiles


class MyWebView(AnkiWebView):

    def sync_execJavaScript(self, script):
        return sync_execJavaScript(self, script)

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

    def zoom_in(self):
        self.change_zoom_by(1.1)

    def zoom_out(self):
        self.change_zoom_by(1/1.1)

    def change_zoom_by(self, interval):
        currZoom = QWebEngineView.zoomFactor(self)
        self.setZoomFactor(currZoom * interval)

    def wheelEvent(self, event):
        # doesn't work in 2020-05?
        pass

    def eventFilter(self, obj, evt):
        # from aqt.webview.AnkiWebView
        #    because wheelEventdoesn't work in 2020-05?


        # disable pinch to zoom gesture
        if isinstance(evt, QNativeGestureEvent):
            return True

        ###my mod
        # event type 31  # https://doc.qt.io/qt-5/qevent.html
        # evt.angleDelta().x() == 0   =>  ignore sidecroll 
        elif evt.type() == QEvent.Wheel and evt.angleDelta().x() == 0 and (mw.app.keyboardModifiers() & Qt.ControlModifier): 
            dif = evt.angleDelta().y()
            if dif > 0:
                self.zoom_out()
            else:
                self.zoom_in()
        ### end my mode

        elif evt.type() == QEvent.MouseButtonRelease:
            if evt.button() == Qt.MidButton and isLin:
                self.onMiddleClickPaste()
                return True
            return False
        return False


class MyDialog(QDialog):
    def __init__(self, parent, bodyhtml, jsSavecommand, wintitle, dialogname):
        super(MyDialog, self).__init__(parent)

        self.jsSavecommand = jsSavecommand
        self.setWindowTitle(wintitle)
        self.resize(810, 1100)
        restoreGeom(self, "805891399_winsize")

        mainLayout = QVBoxLayout()
        mainLayout.setContentsMargins(0, 0, 0, 0)
        mainLayout.setSpacing(0)
        self.setLayout(mainLayout)
        self.web = MyWebView(self)
        self.web.allowDrops = True   # default in webview/AnkiWebView is False
        self.web.title = dialogname
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

        zoomIn_Shortcut = QShortcut(QKeySequence("Ctrl++"), self)
        zoomIn_Shortcut.activated.connect(self.web.zoom_in)

        zoomOut_Shortcut = QShortcut(QKeySequence("Ctrl+-"), self)
        zoomOut_Shortcut.activated.connect(self.web.zoom_out)

        self.web.stdHtml(bodyhtml, cssfiles, jsfiles)

    def onAccept(self):
        global editedfieldcontent
        editedfieldcontent = self.web.sync_execJavaScript(self.jsSavecommand)
        self.web = None  # doesn't remove?
        # self.web._page.windowCloseRequested()  # native qt signal not callable
        # self.web._page.windowCloseRequested.connect(self.web._page.window_close_requested)
        saveGeom(self, "805891399_winsize")
        self.accept()
        # self.done(0)

    def onReject(self):
        ok = askUser("Close and lose current input?")
        if ok:
            saveGeom(self, "805891399_winsize")
            self.reject()

    def closeEvent(self, event):
        ok = askUser("Close and lose current input?")
        if ok:
            event.accept()
        else:
            event.ignore()


def _onWYSIWYGUpdateField(editor):
    if not isinstance(editedfieldcontent, str):
        tooltip("Unknown error in Add-on. Aborting ...")
        return
    editor.note.fields[editor.myfield] = editedfieldcontent
    if not editor.addMode:
        editor.note.flush()
    editor.loadNote(focusTo=editor.myfield)


def on_WYSIWYGdialog_finished(editor, status):
    if status:
        editor.saveNow(lambda e=editor: _onWYSIWYGUpdateField(e))


hiliters_tinymce5 = """
    // TODO change to class applier
    hilite(editor, tinymce, 'hiliteGreen',"#00ff00",'alt+w','GR');
    hilite(editor, tinymce, 'hiliteBlue',"#00ffff",'alt+e','BL'); 
    hilite(editor, tinymce, 'hiliteRed',"#fd9796",'alt+r','RE'); 
    hilite(editor, tinymce, 'hiliteYellow',"#ffff00",'alt+q','YE');
"""


def wysiwyg_dialog(editor, field, editorname):
    if editorname == "T5":
        jssavecmd = "tinyMCE.activeEditor.getContent();"
        wintitle = 'Anki - edit current field in TinyMCE5'
        dialogname = "tinymce5"
        bodyhtml = templatecontent_tinymce5 % {
            "FONTSIZE": gc('fontSize'),
            "FONTNAME": gc('font'),
            "CUSTOMBGCOLOR": "" if theme_manager.night_mode else """this.getDoc().body.style.backgroundColor = '#e4e2e0'""",
            #  https://www.tiny.cloud/blog/dark-mode-tinymce-rich-text-editor/
            "CONTENTCSS": '"dark",' if theme_manager.night_mode else "",
            "SKIN": "oxide-dark" if theme_manager.night_mode else "oxide",
            "THEME": "silver",
            "HILITERS": hiliters if gc("show background color buttons") else "",
            "CONTENT": editor.note.fields[field],
            }
    if editorname == "cked4":
        jssavecmd = "CKEDITOR.instances.cked4_editor.getData();" #""cked4_editor.getData();"
        wintitle = 'Anki - edit current field in ckEditor4'
        dialogname = "cked4"
        bodyhtml = templatecontent_cked4 % {
            "FONTSIZE": gc('fontSize'),
            "FONTNAME": gc('font'),
            "BASEURL": f"http://127.0.0.1:{mw.mediaServer.getPort()}/",
            "CUSTOMBGCOLOR": "#2f2f31" if theme_manager.night_mode else "#e4e2e0",
            "CUSTOMCOLOR": "white" if theme_manager.night_mode else "black",
            "SKIN": "moono-dark" if theme_manager.night_mode else "moono",
            "CONTENT": editor.note.fields[field],
            }
    d = MyDialog(None, bodyhtml, jssavecmd, wintitle, dialogname)
    # exec_() doesn't work, see  https://stackoverflow.com/questions/39638749/
    #d.finished.connect(editor.on_WYSIWYGdialog_finished)
    d.finished.connect(lambda status, func=on_WYSIWYGdialog_finished, e=editor: func(e, status))
    d.setModal(True)
    d.show()
    d.web.setFocus()



def readfile(file):
    filefullpath = os.path.join(addon_path, file)
    with io.open(filefullpath, 'r', encoding='utf-8') as f:
        return f.read()
templatecontent_tinymce5 = readfile("template_tiny5_body.html")
templatecontent_cked4 = readfile("template_cked4_body.html")


def external_editor_start(editor, editorname):
    if editor.currentField is None:
        tooltip("no field focussed. Aborting ...")        
        return
    editor.myfield = editor.currentField
    editor.saveNow(lambda e=editor, f=editor.myfield, n=editorname: wysiwyg_dialog(e,f,n))


def keystr(k):
    key = QKeySequence(k)
    return key.toString(QKeySequence.NativeText)


def setupEditorButtonsFilter(buttons, editor):
    cut_T5 = gc("shortcut: open dialog")
    tip_T5 = "edit current field in external window"
    if cut_T5:
        tip_T5 += " ({})".format(keystr(cut_T5))

    cut_cked4 = gc("Ckeditor4 - shortcut")
    tip_cked4 = "edit current field in ckeditor4"
    if cut_cked4:
        tip_cked4 += " ({})".format(keystr(cut_cked4))

    arglist = [
        #  0                          1          2          3            4       5
        # show                     shortcut    tooltip   functionarg    cmd     icon 
        [True,                     cut_T5,    tip_T5,     "T5"     ,  "T5",      None],
        [gc("Ckeditor4 - enable"), cut_cked4, tip_cked4,  "cked4"  ,  "c4",      None]
    ]

    for line in arglist:
        if not line[0]:
            return
        b = editor.addButton(
            icon=line[5],  # os.path.join(addon_path, "icons", "tm.png"),
            cmd=line[4],
            func=lambda e=editor,n=line[3]: external_editor_start(e, n),
            tip=line[2],
            keys=keystr(line[1]) if line[1] else ""
            )
        buttons.append(b)

    return buttons
addHook("setupEditorButtons", setupEditorButtonsFilter)
