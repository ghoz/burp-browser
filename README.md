Burp-Browser
============
`Burp-Browser` is  a simple gui wrapper for [Burp](http://burp.grke.org/), The Backup and Restore Program.  
It started as a proof of concept and it has outgrown to a *mostly* usable tool.  

What it is not
--------------
  * `Burp-Browser` is not a way to monitor or manage your burp architecture, [burp-ui](https://git.ziirish.me/ziirish/burp-ui) is what you're looking for.
  * Even if `burp-browser` is not supposed to be able to destroy anything, I cannot make any waranty regarding it's use : if it breaks or destroys your data, you get to keep the pieces.
  * `burp-browser` has been tested with burp 1.3.48 . It heavily relies on `burp` output, so any change of format may break the app, please test before deploying.

Requirements
------------
 * [Python](http://python.org) 2.x (tested with 2.7.8)
 * [Pyside](http://qt-project.org/wiki/Get-PySide) QT binding for Python , tested with 1.2.2
 * [Burp](http://burp.grke.org/) BackUp and Restore Program 1.3.48

Installation
-----------
`burp-browser` is just a single python script so beside the requirements, no installation is needed.

Usage
-----
### Launching
  * Run `burp-browser.py` as a user that has the rights to read `burp` config files and certificates .
    * For windows you may need to `run as administrator` a command prompt :  `C:\python27\python.exe path\to\burp-browser.py`
    * for linux `sudo python path/to/burp-browser.py`

### Browsing / Searching
  * By default `burp-browser` will list a tree with all backups avaiable for the current client using default `burp.conf` configuration.
    * navigate the tree, it may be slow depending on your connection to th burp server
  * Search is case insensitive, accepts a file or folder name, and recognises '*' and '?'
    * Avoid using `*` or `*.*` , `burp-browser` will most likely barf if you have too may files in your backup.

### Burp config file / Client Name
  * You may use an alternative burp config by changing the `config file`
  * If your client is allowed to restore files from another client using burp `restore_client` option, you can specify the alternate client name to browse its backups.

## Restoring
  * Once you found the file or folder you want to restore, a right click on it will prompt for a restore path.

Bugs and limitations
--------------------
`burp-browser`really is a quickstop gap to help non techies access burp power as such, 
- it has been tested on Windows only, but it should run on linux.
- it's just a wrapper around `burp` so just as burp, it won't work if a backup is already running,
- sizes returned by burp are funky , so don't trust the sizes ...
- it does not check return values from burp (it returns a-ok in windows 1.3.48 anyway)
- it will crash and burn with huge number of file or if you search for '*' with deep trees
- the UI freezes during restore of huge files,
- non latin/ utf caracters handling is buggy => will hang/crash

License
-------
`burp-browser` is licensed under GPLv2
