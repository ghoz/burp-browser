#!/usr/bin/env python
# encoding: utf-8
# BackUp and Restore Browser
# burp-browser v0.01
# (c) 2014 Ghozlane TOUMI <g.toumi@gmail.com>

# known bugs
# BUG non latin/ utf caracters handling is buggy => will hang
# BUG do no check return values from burp (it returns a-ok in windows 1.3.48 anyway)
# BUG Will crash and burn with huge number of file or if you search for '*' with deep tree
# BUG will Hang during restore of huge files


import sys
import subprocess
import os
import platform
import re
#import traceback # DEBUG
import json

#from pprint import pprint  # DEBUG

from subprocess import PIPE
from PySide import QtCore, QtGui

# custom treeWidget to overide right click
class MyTreeWidget(QtGui.QTreeWidget):
     def __init__(self, parent=None):
         QtGui.QTreeWidget.__init__(self, parent)
         self.contextRun=None
         
     def contextMenuEvent(self, event) : # custom right click .that hurts http://www.riverbankcomputing.com/pipermail/pyqt/2010-December/028860.html
        item=self.itemAt(event.pos())
        if item and self.contextRun :
            self.contextRun(item)
        event.accept()
    
     def mousePressEvent(self, event) :   # Disable right click acting as a normal click OMGWTFBBQ http://qt-project.org/faq/answer/how_to_prevent_right_mouse_click_selection_for_a_qtreewidget       
        if event.button()==QtCore.Qt.RightButton :
            return
        else :
            QtGui.QTreeWidget.mousePressEvent(self,event)

class Ui_MainWindow(object):
     
    # custom QTreeWidgetItem ItemType
    TYPE_BACKUP = QtGui.QTreeWidgetItem.UserType
    TYPE_DRIVE  = QtGui.QTreeWidgetItem.UserType+1
    TYPE_FOLDER = QtGui.QTreeWidgetItem.UserType+2
    TYPE_FILE   = QtGui.QTreeWidgetItem.UserType+3
    
    def setupUi(self, MainWindow):
        MainWindow.resize(640, 480)
        self.centralwidget = QtGui.QWidget(MainWindow)
        self.chooseconf = QtGui.QPushButton("Config file")
        self.chooseconf.clicked.connect(self.setConfigFile)
        self.client = QtGui.QLineEdit()
        self.client.setPlaceholderText('Client Name')
        self.client.editingFinished.connect(self.setClientName)
        self.refresh = QtGui.QPushButton("Clear")
        self.refresh.clicked.connect(self.fillBackups)
        #self.refresh.clicked.connect(lambda : self.fillFullTree (self.bklist.currentText()) ) # TEST Full listing
        self.test = QtGui.QPushButton("Test")
        self.test.clicked.connect(self.restore)
        
        #self.tree = QtGui.QTreeView() # FIXME one day use a cleaner view/model
        self.tree = MyTreeWidget()
        self.tree.setHeaderLabels(['Name', 'Date Modified', 'Size'])
        self.tree.header().setStretchLastSection(False)
        self.tree.header().setResizeMode(0,QtGui.QHeaderView.Stretch)
        self.tree.setColumnWidth(1,120)
        self.tree.contextRun=self.restore # hack
        self.tree.itemClicked.connect(self.on_tree_clicked)  # click
        self.tree.itemActivated.connect(self.on_tree_clicked)  # Enter or doubleclick
        
        self.console = QtGui.QPlainTextEdit()
        self.console.setLineWrapMode(QtGui.QPlainTextEdit.NoWrap)
        self.console.setMaximumBlockCount(1000)
        self.console.setReadOnly(True)
        
        # tries to enable autoscroll
        self.console.moveCursor(QtGui.QTextCursor.End) # BUG not working
        hsb=self.console.horizontalScrollBar() # BUG not working either
        hsb.setValue(hsb.minimum())
        vsb=self.console.verticalScrollBar()
        vsb.setValue(vsb.maximum())
        
        font = QtGui.QFont("monospace")
        font.setStyleHint(QtGui.QFont.TypeWriter)
        self.console.setFont(font)

        #Search
        self.bklist = QtGui.QComboBox()
        self.bklist.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
        self.search = QtGui.QLineEdit()
        self.search.setPlaceholderText('Search')
        self.search.returnPressed.connect(
            lambda: self.fillSearch(self.bklist.currentText(), self.search.text()))

        self.runcmd = QtGui.QPushButton('Search')
        self.runcmd.clicked.connect(
            lambda: self.fillSearch(self.bklist.currentText(), self.search.text()))

        self.debugbox = QtGui.QHBoxLayout()
        self.debugbox.addWidget(self.bklist)
        self.debugbox.addWidget(self.search)
        self.debugbox.addWidget(self.runcmd)

        self.hbox = QtGui.QHBoxLayout()
        self.hbox.addWidget(self.chooseconf)
        self.hbox.addWidget(self.client)
        self.hbox.addWidget(self.refresh) 

        # main browseable area
        self.hsplitter = QtGui.QSplitter()
        self.hsplitter.setChildrenCollapsible(0)
        self.hsplitter.addWidget(self.tree)

        self.vsplitter = QtGui.QSplitter()
        self.vsplitter.setOrientation(QtCore.Qt.Vertical)
        self.vsplitter.addWidget(self.hsplitter)
        self.vsplitter.addWidget(self.console)
        self.vsplitter.setCollapsible(0, 0)

        self.vbox = QtGui.QVBoxLayout(self.centralwidget)
        self.vbox.addLayout(self.debugbox)
        self.vbox.addLayout(self.hbox)
        self.vbox.addWidget(self.vsplitter)

        self.statusbar = QtGui.QStatusBar(MainWindow)

        MainWindow.setStatusBar(self.statusbar)
        MainWindow.setCentralWidget(self.centralwidget)

        # State
        self.restorePath = '' # last backup destination
        self.configPath=''  # last config file path
        self.clientName=''  # last client name 
        self.__isrunning=False # current running state

        # icon provider to get Qt default file/folder Icons
        self.qfip = QtGui.QFileIconProvider()
        # Buurp
        self.bc = BurpCommand(logger=self.console.appendHtml,
                    status=self.statusbar.showMessage)
                    #status=lambda x: self.statusbar.showMessage(x,5000))

        # FIXME Lang / trad
        #    self.retranslateUi(MainWindow)
        #    QtCore.QMetaObject.connectSlotsByName(MainWindow)

    # Lang
    #  def retranslateUi(self, MainWindow):
    #    MainWindow.setWindowTitle(QtGui.QApplication.translate("MainWindow", "MainWindow", None, QtGui.QApplication.UnicodeUTF8))
    #    self.label.setText(QtGui.QApplication.translate("MainWindow", "Hello World!", None, QtGui.QApplication.UnicodeUTF8))


    # FIXME : move everything to controller

    # Change config file
    def setConfigFile(self) : 
        if platform.system() == 'Windows' :
            defaultConfigPath=r'c:\program files\burp'
        else :
            defaultConfigPath='/etc/burp/'
        lastConfigPath=self.configPath or defaultConfigPath
        conf=QtGui.QFileDialog.getOpenFileName(None,'Burp Client config file', lastConfigPath, r'Config Files (*.conf);;All (*.*)')
        if not conf[0] :
            return
        self.configPath=os.path.dirname(conf[0]) # keep last path
        self.chooseconf.setToolTip(conf[0])
        self.bc.config=conf[0]
        self.fillBackups()

    # Disable actionswhen running
    # Yay decorators! SO 8218900
    def waiting(func) :
        def run(self, *args) :
            if self.__isrunning : # already running
                return
            self.__isrunning=True
            self.search.setEnabled(False)
            self.client.setEnabled(False)
            self.chooseconf.setEnabled(False)
            self.refresh.setEnabled(False)
            self.runcmd.setEnabled(False)
            self.statusbar.clearMessage()
            QtGui.qApp.setOverrideCursor(QtCore.Qt.WaitCursor)
            QtGui.qApp.processEvents()

            func(self,*args)
            
            self.search.setEnabled(True)
            self.client.setEnabled(True)
            self.chooseconf.setEnabled(True)
            self.refresh.setEnabled(True)
            self.runcmd.setEnabled(True)
            QtGui.QApplication.restoreOverrideCursor()
            self.__isrunning=False
            
        return run
          
    def setClientName(self) : 
        newClientName=self.client.text()
        if newClientName == self.clientName : # same client Name
            return
        self.clientName=newClientName
        self.bc.client=newClientName
        self.fillBackups()

    @waiting
    def on_tree_clicked(self, item, column):
        pathlist = []
        path = ''
        clickeditem = item # FIXME change name :treeItem?
        # don't fetch sublevel if already populated or isaFile
        if (clickeditem.foreground(0) == QtCore.Qt.black ) : # FIXME Uuuuglyyy => subclass treewidgetitem?
            clickeditem.setExpanded(not clickeditem.isExpanded() )  
            return
        while item.parent():
            #print item.text(0)
            pathlist.insert(0, item.text(0))
            pathlist.insert(0, '/')
            item = item.parent()
        path = ''.join(pathlist[1:])
        #print path
        backupTxt = item.text(0)
        m = re.match('^(\d*)\s',backupTxt) #get backup Num FIXME 
        bknum = m.group(1)        
        data=self.bc.listDir(bknum,path)
        self.buildSubTree(clickeditem,data)          
        clickeditem.setExpanded(True)  


    @waiting
    def restore(self,item,column=0) :
        pathlist=[]
        dir = QtGui.QFileDialog.getExistingDirectory(None, \
                "Restore to", self.restorePath)
        if not dir :
          return
        self.restorePath=dir
        if item.type() != self.TYPE_FILE  : #Folder or drive : adds a trailing / for restore
            pathlist.append ('/')
        # rebuild path bottom up
        while item.parent():
            #print item.text(0)
            pathlist.insert(0, item.text(0))
            pathlist.insert(0, '/')
            item = item.parent()
        path = ''.join(pathlist[1:])
        #print path # DEBUG
        backupTxt = item.text(0)
        m = re.match('^(\d*)\s',backupTxt) # FIXME 
        bknum = m.group(1)        
        
        self.bc.restoreTo(bknum, path, dir)

    @waiting
    def fillBackups(self):
        # clear tree
        self.tree.clear()
        # build drop down list
        self.bklist.clear()
        for bkname in self.bc.getBackups()  :
            self.bklist.insertItems(0, [ re.match(r'\d*',bkname).group(0)])
        self.bklist.insertItems(0, ["all"])
        self.bklist.setCurrentIndex(1)
        # Rebuild tree
        data=self.bc.listBackups()
        #pprint(data) # DEBUG
        self.buildFullTree(data)
        
    @waiting
    def fillSearch(self, bknum=None, glob=None):
        if  not glob:
            return 
        # using burp -b a returns invalid json => loop
        if  not bknum or bknum=="all" : # search all backups
            for bk in reversed(self.bc.getBackups()): # FIXME extract bk num from bkname 
                self.fillSearch(bk,glob)
            return
        data=self.bc.searchGlob(bknum,glob)
        #pprint(data) # DEBUG
        self.buildFullTree(data)
    
    @waiting
    def fillFullTree(self, bknum=None) : 
        if not bknum :
            return
        data=self.bc.listFull(bknum)
        self.buildFullTree(data,False)

    def buildSubTree(self, treeItem, data) :
        #burp -d returns short names => build subtree only
        treeItem.setForeground(0,QtCore.Qt.black)
        rawitems = data.get('items', [])
        for item in rawitems:
            if item['type'] not in ['d', 'f']:  # Folder /files only
                continue
            name=item['name'] # short name, no path
            found=False
            for j in range(0, treeItem.childCount()): 
                if name == treeItem.child(j).text(0):  # found parent
                    found = True
                    break
            if found:  # already exists , next
                continue
            # FIXME copy paste job re buildSubTree/buildFullTree
            # looks like a drive (X:), FIXME test for level == 2 ( below backupname)
            if re.match(r'^\w:$',name):
                newTreeItem=QtGui.QTreeWidgetItem(treeItem,self.TYPE_DRIVE)
                newTreeItem.setIcon(
                    0, self.qfip.icon(QtGui.QFileIconProvider.Drive))
                newTreeItem.setForeground(0,QtCore.Qt.darkGray)
            # file
            elif item['type'] == 'f' :  # File
                newTreeItem=QtGui.QTreeWidgetItem(treeItem,self.TYPE_FILE)
                newTreeItem.setIcon(
                    0, self.qfip.icon(QtGui.QFileIconProvider.File))
                # BURP-BUG  : crazy sizes??
                newTreeItem.setText(2, str(item['st_size']))
                newTreeItem.setTextAlignment(2, QtCore.Qt.AlignRight)
                newTreeItem.setForeground(0,QtCore.Qt.black)
            else : # Folder
                newTreeItem=QtGui.QTreeWidgetItem(treeItem,self.TYPE_FOLDER)
                newTreeItem.setIcon(
                    0, self.qfip.icon(QtGui.QFileIconProvider.Folder))
                newTreeItem.setForeground(0,QtCore.Qt.darkGray)
            newTreeItem.setText(0,name)
            newTreeItem.setData(1, QtCore.Qt.DisplayRole, QtCore.QDateTime().fromTime_t(item['st_mtime']))
            
    def buildFullTree(self, data, partial=True):
        if partial : # we were given a paritial tree : gray out path
            foreground=QtCore.Qt.darkGray
        else : 
            foreground=QtCore.Qt.black
        
        rawbackup = data['backup']['timestamp']
        rawitems = data.get('items', []) # use get rather than [] to avoid exception if empty 
        for item in rawitems:
            if item['type'] not in ['d', 'f']:  # only Folders/Files
                continue
            #print item['name'] # DEBUG : fullname  
            tokens = item['name'].split('/')
            # Hack for listbackup : hand made json 
            # has no timestamp
            if rawbackup != '':
                tokens = [rawbackup] + tokens # adds backup num

            #pprint (tokens) # DEBUG
            # hack : backupname is  0000015 2014-10-07 12:27:08 (deletable) => 0000015 (deletable) + 2014-10-07 12:27:08
            # FIXME do that somewhere else ?
            mbk = re.match(
                r'^(\d*\s*)(\d\d\d\d-\d\d-\d\d \d\d:\d\d:\d\d)\s*(.*)', tokens[0])
            # FIXME : add exception if no match
            backup_name = mbk.group(1) + mbk.group(3)
            backup_time = QtCore.QDateTime().fromString(
                mbk.group(2), 'yyyy-MM-dd HH:mm:ss')

            # splits path to populate the treeview
            parent = None
            # checks  top level
            for i in range(0, self.tree.topLevelItemCount()):
                if self.tree.topLevelItem(i).text(0) == backup_name :
                    # found !
                    parent = self.tree.topLevelItem(i)
                    break
            if not parent:  # no toplevel item, create one
                parent = QtGui.QTreeWidgetItem(None, [backup_name], self.TYPE_BACKUP)
                parent.setData(1, QtCore.Qt.DisplayRole, backup_time)
                parent.setIcon(0, self.qfip.icon(QtGui.QFileIconProvider.Computer))
                parent.setForeground(0,QtCore.Qt.darkGray)
                self.tree.insertTopLevelItem(0, parent)
            # starting for 2nd level , check level by level check of subdir already exists and create if needed
            for idx, token in enumerate(tokens[1:]):
                found = False
                # Check sublevel
                for j in range(0, parent.childCount()):
                    if token == parent.child(j).text(0):  # found parent
                        parent = parent.child(j)
                        found = True
                        break
                if found:  # already exist. next
                    continue
                # create new entry
                # 1st level , looks like  X: : is a windows drive
                if idx == 0 and re.match(r'^\w:$',token):
                    parent = QtGui.QTreeWidgetItem(parent, [token], self.TYPE_DRIVE)
                    parent.setIcon(
                        0, self.qfip.icon(QtGui.QFileIconProvider.Drive))
                    parent.setForeground(0,foreground)
                # path created and isafile 
                elif idx == len(tokens[1:-1]) and item['type'] == 'f':
                    parent = QtGui.QTreeWidgetItem(parent, [token], self.TYPE_FILE)
                    parent.setIcon(
                        0, self.qfip.icon(QtGui.QFileIconProvider.File))
                    parent.setText(2, str(item['st_size']))
                    parent.setTextAlignment(2, QtCore.Qt.AlignRight)
                    parent.setForeground(0,QtCore.Qt.black)
                else: # is a folder
                    parent = QtGui.QTreeWidgetItem(parent, [token], self.TYPE_FOLDER)
                    parent.setIcon(
                        0, self.qfip.icon(QtGui.QFileIconProvider.Folder))
                    parent.setForeground(0,foreground)
                parent.setText(0, token)

                # BUG for search date of folders are false ... ...
                parent.setData(
                    1, QtCore.Qt.DisplayRole, QtCore.QDateTime().fromTime_t(item['st_mtime']))

class ControlMainWindow(QtGui.QMainWindow):

    def __init__(self, parent=None):
        super(ControlMainWindow, self).__init__(parent)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.ui.fillBackups() # run on start with defaults
    # FIXME Controller should control. <insert lolcat GIF Here> Controller is not amused.

class BurpCommand (object):
    def defaultLogger(self,str):
        print (str)

    def __init__(self, logger=None, status=None):
        self.logger=logger or self.defaultLogger    # logs
        self.status=status or self.defaultLogger    # print status / status bar
        if platform.system() == 'Windows' :
            self.__burp = r'c:\program files\burp\bin\burp.exe'
        else :
            self.__burp = '/usr/sbin/burp' # FIXME : rather dumb... search for burp following PATH?
        self.__config='' # current config file
        self.__client='' # current client name when using clien can restore option
        #
        self.lastMessage=''

        # TODO ugly. refactor to filtering/analysis class ?
        ## Burp Messages
        # 2014-10-29 22:59:29: c:\program files\burp\bin\burp.exe[10636] before client
        self.__pLog = re.compile(r'^(?P<date>\d{4}-\d\d-\d\d) (?P<time>\d\d:\d\d:\d\d): (?P<burp>[^[]*)\[(?P<pid>\d*)\] (?P<message>.*)$',re.I)

        ## Burp Errors
        # expected r cmd - got e:backup not found
        # expected 'c:ok', got 'e:another instance is already running'
        # expected 'c:orig_client ok', got 'e:Access to client is not allowed: eat-srv-sql'
        # expected 'c:orig_client ok', got 'e:Could not load alternate config: eat-srv-sql2'
        # problem with auth: got e unable to authorise on server
        self.__pErr = re.compile(r'(?:expected|problem).*got\s*\'?e:?(?P<error>.*)')
        self.__pOk = re.compile(r'ok')

        ## JSON maybe?
        self.__pJSON = re.compile(r'^\s*[,{}\[\]"]')
        self.__pName = re.compile(r'^\s*"name"\s*:\s*"(?P<name>.*)"')

        ## Backup list
        # Backup: 0000027 2014-10-22 12:07:21 (deletable)
        # Backup: 0000028 2014-10-23 12:07:23
        self.__pBackup = re.compile(r'^Backup:\s*(?P<backup>.*)\s*')

        # local cache
        self.__backups=[]

    @property
    def config(self) : 
        #print "get config"+ self._config # DEBUG
        return self.__config

    @config.setter
    def config(self,value) : # FIXME check config file exists or empty (default)
        #print "set config"+ value   # DEBUG
        self.__config=value
        self.__backups=[] # reset backups cache

    @property
    def client(self) : 
        #print "get config"+ self._config # DEBUG
        return self.__client

    @client.setter
    def client(self,value) : # FIXME check client name : [0-9a-Z-_.] or empty (default =self)
        self.__client=value
        self.__backups=[] # reset backups cache

    # FIXME get/setter for burp path? + check burp path

    def burpArgs(self): #TODO rename '_xx' :internal
        args=[]
        if self.__config :
            args=args+['-c', self.__config]
        if self.__client :
            args=args+['-C', self.__client]
        return args

    def getVersion(self):
        self.version=[]
        self.runBurp(['-v'], [self.filterVersion])
        return self.version

    def getBackups(self): # no JSon mode in 1.3.48 => get backups
        if self.__backups :  # list of backup names strings 
            return self.__backups 
        args=['-a', 'l']+ self.burpArgs()
        self.runBurp(args,filters=[self.filterMessage,self.filterBackup])
        return self.__backups

    def listBackups(self) : # builds fake json from backup list
        json_str = ''' {
            "backup": {
                "timestamp": ""
            },
            "items": [ '''

        json_str += ','.join(['{"type": "d","name": "' + bk + '"}' for bk in self.getBackups()])
        json_str += '] }'
        return json.loads(json_str)

    def listDir(self,backup,path): # get sublevel : ls -l
        # empty = list 1st level
        self.__json=[]
        args=['-a', 'L', '-j', '-b', backup, '-d', path] + self.burpArgs()
        # gets sublevel
        self.runBurp(args,filters=[self.filterMessage,self.filterJson])

        #FIXME copypaste
        # string to json. bourrin, if you pardon my french
        json_str = '\n'.join(self.__json)
        json_str= self.fixJson(json_str)
        try :
            data=json.loads(json_str)
        except:
            print ("BAD JSON : ")
            print (json_str)
            data={}
        return data

    def searchGlob(self,backup,glob): # find glob : find -iname 
        self.__json=[]
        if not backup:
            return # throw error ?
        if not glob:
            return # throw error ?
        # glob => regex        
        # \ => / : fix windows path
        glob=glob.replace('\\', '/')
        # escape everything, []{}()+*.?^$
        glob=re.escape(glob)
        # * => [^/]* : everything but path separator
        # ? => .    : one char
        glob=glob.replace(r'\*', '[^/]*').replace(r'\?', '.')
        # C: => C. bug regexp with ':'
        glob=glob.replace(r'\:', '.')
        # a => [aA] : case insenstive eveything
        def ul(match) :
            return '['+ match.group(1).upper() + match.group(1).lower() + ']'
        glob=re.sub(r'([a-zA-Z])',ul,glob)

        args=['-a', 'L', '-j', '-r', glob+'$', '-b', backup] + self.burpArgs()

        # Returns full path
        self.runBurp(args,filters=[self.filterMessage,self.filterJson])
        json_str = '\n'.join(self.__json)
        json_str=self.fixJson(json_str)
        try :
            data=json.loads(json_str)
        except:
            print ("BAD JSON : ")
            print (json_str)
            data={}
        return data

    def listFull(self,backup): # get full ls ls -lr
        #BUG WILL explode when getting lots and lots of files..  t'is only a huge string y'know
        self.__json=[]
        if not backup: # check :number only
            return # throw error ?

        args=['-a', 'L', '-j', '-b', backup] + self.burpArgs()
        self.runBurp(args,filters=[self.filterMessage,self.filterJson])
        
        json_str = '\n'.join(self.__json)
        json_str=self.fixJson(json_str)
        try :
            data=json.loads(json_str)
        except:
            print ("BAD JSON : ")
            print (json_str)
            data={}
        return data

    def restoreTo(self,backup,path,destination) :
        #print "RESTORE bk " +backup + " " + path + " to "+ destination # DEBUBG
        #Windows -> unix
        path=path.replace('\\', '/')
        strip=path.count('/')
        path=re.escape(path)
        if path.endswith('/') : # folder restore
            path='^'+path
            strip=strip-1
        else : # file
            path='^' + path + '$'
            
        args=['-a', 'r', '-b' , backup, '-r', path, '-d', destination, '-s', str(strip)] + self.burpArgs()
        self.runBurp(args)
    
    # BURP-BUG a search returns no items , returns bad Json : trailing ','
    def fixJson (self, str) :
     return re.compile(r'\},[\r\n]*\s*\}',re.MULTILINE) \
                       .sub('}}',str)
                       
    # extract Burp messages
    def filterMessage(self,line) :
        match = self.__pLog.match(line)
        if not match :
            return 0 
        self.logger(line)
        self.lastMessage=match.group('message')
        
        matchError= self.__pErr.search(self.lastMessage)
        matchOK=self.__pOk.search(self.lastMessage)
        if matchError:
            self.__burpError=1
            self.status(self.lastMessage)
        elif matchOK:
            self.__burpError=0
            self.status(self.lastMessage)
        return 1

    # looks like JSON : it must be JSON !
    def filterJson (self,line) :
        match = self.__pJSON.search(line)
        if not match :
            return 0
        if re.search(r'^\s*"regex":',line) :
            line=line.replace("\\","\\\\") # BURP-BUG 1.3.48 : regexp is not properly escaped \ => \\
        self.__json.append(line)
        #prints name only
        matchName = self.__pName.match(line)
        if matchName:  # match json "name"
            self.logger('Name : ' + matchName.group('name'))
        #self.logger("<pre>"+line+"</pre>") # DEBUG verbose : full JSON
        return 1

    # grok standard burp messages 
    def filterBackup(self, line) :
        match = self.__pBackup.match(line)
        if not match :
            return 0
        self.__backups.append(match.group('backup'))
        self.logger(line)
        return 1
    
    # get burp version
    def filterVersion(self,line) :
    #C:\Program Files\Burp\bin\burp.exe-1.3.48
        if line.startswith(self.__burp + '-') : 
            versionString=line[len(self.__burp + '-'):]
            self.logger("Version: " +versionString )
            self.version=versionString.split('.')
            return 1
        return 0

    # catchall Filter : unknown lines
    def filterUnknown(self,line) :
       self.logger('<strong><em>'+line+'</em><strong>')
       self.ungroked+=1

    # run burp, filters line by line to grok output
    def runBurp(self, args, filters=None) :
        #QtGui.QSound.play(r'C:\temp\belching.wav') # Buuurp!
        self.burpError=0
        self.ungroked=0
        
        if not filters :
            filters=[self.filterMessage]
        filters.append(self.filterUnknown)
        #pprint(args) # DEBUG
        #traceback.print_stack() # DEBUG
        self.logger( '"' + '" "'.join([self.__burp] +args) + '"')
        QtGui.qApp.processEvents()
        # BUG with utf8 add an encode / decode pass?
        cmd = subprocess.Popen([self.__burp] + args , stdout=PIPE)
        for line in cmd.stdout :
            for matchFilter in filters :
                if matchFilter(line.rstrip('\r\n')) :
                    break
            QtGui.qApp.processEvents()
        cmd.communicate()  # closes stdout , cmd clean exit ?

if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    mySW = ControlMainWindow()
    mySW.show()

#    bc = BurpCommand(logger=mySW.ui.console.appendHtml,
##                     status=mySW.ui.statusbar.showMessage)
#                     status=lambda x: mySW.ui.statusbar.showMessage(x,1000))
#    bc = BurpCommand(logger=mySW.ui.console.appendPlainText)
#    bc.config=r'c:\program files\burp\burp.conf'
#    bc.client='test-client'
#    bc.getVersion()
#    bc.getBackups()
#    bc.listDir('33',r'C:/Users')
#    bc.searchGlob('33',r'outlook.pst')
#
## Non existent path
#    bc.listDir('33',r'c:/temp')
#    bc.searchGlob('33',r'azerty')
## non existent backup
#    bc.listDir('133',r'')

    sys.exit(app.exec_())
 