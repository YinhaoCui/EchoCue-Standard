"""Translate presentation only; model IDs, prompts and persisted option keys stay canonical."""
import re
import tkinter as tk
from tkinter import ttk, messagebox
from locale_catalog import EN


def owner(widget):
    while widget is not None:
        if hasattr(widget,'_locale'):return widget._locale
        widget=getattr(widget,'master',None)
    return None


class Locale:
    def __init__(self,root,language='en'):
        self.root=root;self.language=language if language in ('en','zh') else 'en'
        self.widgets={};self.bindings={};self.special={};self.callbacks=[];self.raw_variables=set()
        self.pattern=re.compile('|'.join(re.escape(k) for k in sorted(EN,key=len,reverse=True)))
        root._locale=self
        install_hooks()

    def raw_variable(self, value=""):
        """Keep user content out of UI phrase substitution."""
        variable=tk.StringVar(self.root,value=value)
        self.raw_variables.add(str(variable))
        return variable

    def t(self,value):
        if self.language=='zh' or not isinstance(value,str):return value
        if value in EN:return EN[value]
        return self.pattern.sub(lambda match:EN[match.group()],value)

    def options(self,widget,options):
        options=dict(options)
        kind=getattr(widget,'widgetName','')
        allowed=('ttk::label','ttk::button','ttk::checkbutton','ttk::radiobutton','ttk::labelframe','ttk::menubutton',
                 'label','button','checkbutton','radiobutton','labelframe','menubutton','ttk::combobox')
        if kind not in allowed:return options
        saved=self.widgets.setdefault(widget,{})
        for name in ('text','values'):
            if name not in options:continue
            saved[name]=options[name]
            options[name]=tuple(self.t(v) for v in options[name]) if name=='values' else self.t(options[name])
        if 'width' in options and 'text' in options:saved['width']=options['width']
        width=saved.get('width')
        if kind in ('ttk::button','button') and isinstance(width,int) and width>0 and 'text' in options:
            options['width']=max(width,len(self.t(saved['text']))) if self.language=='en' else width
        if 'textvariable' in options and options['textvariable']:
            source=str(options['textvariable'])
            if source in self.raw_variables:return options
            # A configure query may return a display variable; never bind a shadow to itself.
            source=next((k for k,v in self.bindings.items() if str(v['display'])==source),source)
            options['textvariable']=self.shadow(source,kind=='ttk::combobox')
            if kind=='ttk::combobox':widget._locale_source=source
        return options

    def shadow(self,source,two_way=False):
        if source in self.bindings:
            self.bindings[source]['two_way'] |= two_way
            return self.bindings[source]['display']
        display=tk.StringVar(self.root)
        binding={'display':display,'busy':False,'two_way':two_way}
        self.bindings[source]=binding
        def forward(*_):
            if binding['busy']:return
            try:
                binding['busy']=True;display.set(self.t(self.root.globalgetvar(source)))
            except tk.TclError:pass
            finally:binding['busy']=False
        def backward(*_):
            if binding['busy'] or not binding['two_way']:return
            try:
                binding['busy']=True;value=display.get()
                candidates=[]
                for widget,saved in self.widgets.items():
                    if getattr(widget,'_locale_source',None)==source:candidates.extend(saved.get('values',()))
                original=next((v for v in candidates if self.t(v)==value),value)
                self.root.globalsetvar(source,original)
            finally:binding['busy']=False
        command=self.root.register(forward)
        self.root.tk.call('trace','add','variable',source,'write',command)
        display.trace_add('write',backward)
        binding['forward']=forward
        forward();return display

    def remember(self,widget,kind,index,text):
        self.special[(widget,kind,str(index))]=text

    def set_language(self,language):
        self.language=language if language in ('en','zh') else 'en'
        for widget,options in list(self.widgets.items()):
            try:
                if widget.winfo_exists():widget.configure(**options)
                else:self.widgets.pop(widget,None)
            except tk.TclError:self.widgets.pop(widget,None)
        for binding in list(self.bindings.values()):binding['forward']()
        for (widget,kind,index),text in list(self.special.items()):
            try:
                if not widget.winfo_exists():continue
                if kind=='title':widget.title(text)
                elif kind=='tab':widget.tab(index,text=text)
                elif kind=='heading':widget.heading(index,text=text)
                elif kind=='menu':widget.entryconfigure(index,label=text)
            except tk.TclError:pass
        for callback in list(self.callbacks):
            try:callback()
            except tk.TclError:pass


def install_hooks():
    if getattr(tk.Misc,'_audio_localized',False):return
    tk.Misc._audio_localized=True
    original_options=tk.Misc._options
    def options(widget,cnf,kw=None):
        locale=owner(widget)
        merged=tk._cnfmerge((cnf,kw)) if kw else dict(cnf)
        return original_options(widget,locale.options(widget,merged) if locale else merged)
    tk.Misc._options=options
    original_get=ttk.Combobox.get;original_set=ttk.Combobox.set
    def get(widget):
        source=getattr(widget,'_locale_source',None)
        return widget.tk.globalgetvar(source) if source else original_get(widget)
    def set_value(widget,value):
        source=getattr(widget,'_locale_source',None)
        if source:widget.tk.globalsetvar(source,value)
        else:original_set(widget,value)
    ttk.Combobox.get=get;ttk.Combobox.set=set_value
    original_title=tk.Wm.wm_title
    def title(widget,string=None):
        locale=owner(widget)
        if locale and string is not None:
            locale.remember(widget,'title','',string);string=locale.t(string)
        return original_title(widget,string)
    tk.Wm.wm_title=tk.Wm.title=title
    original_add=ttk.Notebook.add;original_tab=ttk.Notebook.tab
    def add(widget,child,**kw):
        locale=owner(widget)
        if locale and 'text' in kw:
            locale.remember(widget,'tab',child,kw['text']);kw['text']=locale.t(kw['text'])
        return original_add(widget,child,**kw)
    def tab(widget,index,option=None,**kw):
        locale=owner(widget)
        if locale and 'text' in kw:
            locale.remember(widget,'tab',index,kw['text']);kw['text']=locale.t(kw['text'])
        return original_tab(widget,index,option,**kw)
    ttk.Notebook.add=add;ttk.Notebook.tab=tab
    original_heading=ttk.Treeview.heading
    def heading(widget,index,option=None,**kw):
        locale=owner(widget)
        if locale and 'text' in kw:
            locale.remember(widget,'heading',index,kw['text']);kw['text']=locale.t(kw['text'])
        return original_heading(widget,index,option,**kw)
    ttk.Treeview.heading=heading
    original_menu_add=tk.Menu.add;original_entry=tk.Menu.entryconfigure
    def menu_add(widget,itemType,cnf={},**kw):
        kw=dict(cnf,**kw);locale=owner(widget);label=kw.get('label')
        if locale and label is not None:kw['label']=locale.t(label)
        result=original_menu_add(widget,itemType,**kw)
        if locale and label is not None:locale.remember(widget,'menu',widget.index('end'),label)
        return result
    def entry(widget,index,cnf=None,**kw):
        locale=owner(widget)
        if locale and (isinstance(cnf,dict) or kw):
            kw=dict(cnf or {},**kw);cnf=None
            if 'label' in kw:
                locale.remember(widget,'menu',widget.index(index),kw['label']);kw['label']=locale.t(kw['label'])
        return original_entry(widget,index,cnf,**kw)
    tk.Menu.add=menu_add;tk.Menu.entryconfigure=tk.Menu.entryconfig=entry
    original_show=messagebox._show
    def show(title=None,message=None,_icon=None,_type=None,**options):
        locale=owner(options.get('parent') or tk._default_root)
        if locale:title,message=locale.t(title),locale.t(message)
        return original_show(title,message,_icon,_type,**options)
    messagebox._show=show
