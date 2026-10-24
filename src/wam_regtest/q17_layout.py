"""Read-only geometry acceptance; visual/operator approval is always separate.

Qt imports are local so the artifact adjudicator needs no GUI runtime.
Only already-public action/status text and disposable-window screenshots leave
the native probe. This module cannot grant Core, custody or signer authority.
"""
import hashlib
import json
import os
from pathlib import Path
import sys


def widget_geometry(widget,window,name):
    from PySide6.QtCore import QPoint,QRect,Qt
    from PySide6.QtWidgets import QComboBox,QPushButton,QStyle,QStyleOptionButton,QStyleOptionComboBox
    if not widget.isVisibleTo(window): raise ValueError('Q17_ESSENTIAL_CONTROL_HIDDEN_'+name)
    outer=QRect(widget.mapTo(window,QPoint(0,0)),widget.size())
    if not window.rect().contains(outer): raise ValueError('Q17_CONTROL_OUTSIDE_WINDOW_'+name)
    hint=widget.sizeHint();fm=widget.fontMetrics()
    if isinstance(widget,QPushButton):
        option=QStyleOptionButton();widget.initStyleOption(option)
        content=widget.style().subElementRect(QStyle.SubElement.SE_PushButtonContents,option,widget)
        text=widget.text();need=fm.horizontalAdvance(text)+(0 if widget.icon().isNull() else widget.iconSize().width())
        height=fm.height()
    elif isinstance(widget,QComboBox):
        option=QStyleOptionComboBox();widget.initStyleOption(option)
        content=widget.style().subControlRect(QStyle.ComplexControl.CC_ComboBox,option,QStyle.SubControl.SC_ComboBoxEditField,widget)
        text=widget.currentText();need=fm.horizontalAdvance(text);height=fm.height()
    else:
        content=widget.contentsRect();text=widget.text()
        need=0 if widget.wordWrap() else fm.horizontalAdvance(text)
        height=fm.boundingRect(QRect(0,0,content.width(),10000),Qt.TextFlag.TextWordWrap,text).height() if widget.wordWrap() else fm.height()
    result={'name':name,'text':text,'enabled':widget.isEnabled(),
        'rect':[outer.x(),outer.y(),outer.width(),outer.height()],
        'size_hint':[hint.width(),hint.height()],
        'content':[content.width(),content.height()],
        'required_text':[need,height],'font_pixel_size':widget.font().pixelSize()}
    if (content.width()<need or content.height()<height
            or isinstance(widget,(QPushButton,QComboBox)) and (widget.width()<hint.width() or widget.height()<hint.height())):
        error=ValueError('Q17_TEXT_CLIPPED_'+name);error.q17_geometry=result;raise error
    return result


def inspect_window(window,app):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QStyleOptionViewItem
    names=['workspace_title','verification_badge','appearance','refresh_button']
    names += [n for n in ('start_core','stop_core') if hasattr(window,n)]
    controls=[widget_geometry(getattr(window,n),window,n) for n in names]
    for i,a in enumerate(controls):
        for b in controls[i+1:]:
            x,y,w,h=a['rect'];u,v,s,t=b['rect']
            if min(x+w,u+s)>max(x,u) and min(y+h,v+t)>max(y,v):
                raise ValueError('Q17_ESSENTIAL_CONTROLS_OVERLAP')
    controls += [widget_geometry(getattr(window,n),window,n) for n in ('status','warning')]
    nav=window.navigation;old=nav.currentRow();scroll=nav.verticalScrollBar().value();navigation=[];hidden=[]
    try:
        for index in range(nav.count()):
            item=nav.item(index)
            if item.isHidden():
                # Managed spending deliberately excludes Core mining authority.
                # Record that policy; never select or reveal the hidden action.
                hidden.append(item.text());continue
            nav.setCurrentRow(index);nav.scrollToItem(item);app.processEvents()
            rect=nav.visualItemRect(item);option=QStyleOptionViewItem();nav.initViewItemOption(option)
            model=nav.model().index(index,0);ideal=nav.itemDelegate().sizeHint(option,model)
            if (not nav.viewport().rect().contains(rect) or ideal.width()>rect.width()
                    or ideal.height()>rect.height() or window.stack.currentIndex()!=index):
                error=ValueError('Q17_NAVIGATION_INACCESSIBLE')
                error.q17_geometry={'control':'navigation','text':item.text(),
                    'rect':[rect.x(),rect.y(),rect.width(),rect.height()],
                    'viewport':[nav.viewport().width(),nav.viewport().height()],
                    'size_hint':[ideal.width(),ideal.height()],
                    'requested_page':index,'actual_page':window.stack.currentIndex()}
                raise error
            navigation.append({'text':item.text(),'rect':[rect.x(),rect.y(),rect.width(),rect.height()],
                'size_hint':[ideal.width(),ideal.height()]})
    finally:
        nav.setCurrentRow(old);nav.verticalScrollBar().setValue(scroll);app.processEvents()
    welcome=[]
    if hasattr(window,'welcome_page'):
        page=window.welcome_page;before=page.scroll.verticalScrollBar().value()
        try:
            for i,button in enumerate((*page.controls,window.recover_runtime_button)):
                page.scroll.ensureWidgetVisible(button);app.processEvents()
                row=widget_geometry(button,window,'welcome-action-'+str(i))
                # All of the actual button, not just its center, must be usable.
                from PySide6.QtCore import QPoint,QRect
                box=QRect(button.mapTo(page.scroll.viewport(),QPoint(0,0)),button.size())
                if not page.scroll.viewport().rect().contains(box):raise ValueError('Q17_SCROLL_ACTION_INACCESSIBLE')
                row.update(scroll_viewport=[page.scroll.viewport().width(),page.scroll.viewport().height()],
                    in_viewport_rect=[box.x(),box.y(),box.width(),box.height()])
                welcome.append(row)
        finally:
            page.scroll.verticalScrollBar().setValue(before);app.processEvents()
    return {'controls':controls,'navigation':navigation,'hidden_navigation':hidden,'navigation_viewport':[nav.viewport().width(),nav.viewport().height()],
        'welcome_actions':welcome}


def capture(window,app,state):
    """Called only by an explicitly opted-in genuine disposable GUI child."""
    from PySide6.QtWidgets import QApplication
    if QApplication.activeModalWidget() is not None:raise ValueError('Q17_NO_DIALOG_CAPTURE')
    allowed={'initial-locked','core-verified-locked','verified-read','verified-spend','runtime-recovery-required','core-not-ready'}
    if state not in allowed:raise ValueError('Q17_STATE_DENIED')
    directory=Path('fusion-ui-review');directory.mkdir(exist_ok=True)
    old_size=window.size();old_mode=window.appearance.currentIndex();records=[]
    try:
        for mode in (1,2):
            window.appearance.setCurrentIndex(mode)
            for width,height in ((1280,800),(820,600)):
                window.resize(width,height)
                for _ in range(3):app.processEvents()
                row=inspect_window(window,app)
                filename=f'q17-{state}-{width}x{height}-{window.appearance.currentData()}.png'
                if not window.grab().save(str(directory/filename)):raise ValueError('Q17_SCREENSHOT_REQUIRED')
                row.update(state=state,requested=[width,height],actual=[window.width(),window.height()],
                    mode=window.appearance.currentData(),screenshot=filename,
                    screenshot_sha256=hashlib.sha256((directory/filename).read_bytes()).hexdigest())
                records.append(row)
        receipt={'schema':'wam-q17-layout/v1','geometry_status':'PASS','visual_approval':'PENDING_REVIEW',
            'physical_approval':'PENDING_OPERATOR','source_head_sha':os.environ.get('WAM_SOURCE_HEAD'),
            'platform':{'darwin':'macos-arm64','win32':'windows-x64','linux':'linux-x86_64'}[sys.platform],
            'execution':'FROZEN' if getattr(sys,'frozen',False) else 'SOURCE_NATIVE',
            'binary_sha256':hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest(),
            'qt_platform':app.platformName(),'device_pixel_ratio':window.devicePixelRatioF(),'state':state,'records':records}
        (directory/('q17-'+state+'.json')).write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n')
        return receipt
    except ValueError as error:
        # Only fixed public action/status geometry, never arbitrary exception
        # arguments or private fixture/log files. Failure still propagates.
        failure={'schema':'wam-q17-layout-failure/v1','state':state,'status':'FAIL',
            'source_head_sha':os.environ.get('WAM_SOURCE_HEAD'),
            'actual':[window.width(),window.height()],
            'geometry':getattr(error,'q17_geometry',{})}
        (directory/('q17-layout-failure-'+state+'.json')).write_text(json.dumps(failure,sort_keys=True,indent=2)+'\n')
        raise
    finally:
        window.resize(old_size);window.appearance.setCurrentIndex(old_mode);app.processEvents()


STATES={'initial-locked','core-verified-locked','verified-read','verified-spend','runtime-recovery-required','core-not-ready'}


def check_component(component,images,platform,source,frozen,binaries=(),dpr=None):
    """Adjudicate byte-bound geometry receipts, never confer visual approval."""
    import struct
    def require(condition):
        if not condition:raise ValueError('Q17_CURRENT_COMPLETE_GEOMETRY_REQUIRED')
    def vector(value,length):
        require(type(value) is list and len(value)==length and all(type(i) is int for i in value))
        return value
    def inside(box,size):
        x,y,w,h=vector(box,4);width,height=vector(size,2)
        return x>=0 and y>=0 and w>0 and h>0 and x+w<=width and y+h<=height
    require(type(component) is dict and component.get('schema')=='wam-q17-layout-component/v1'
        and component.get('geometry_status')=='PASS' and component.get('visual_approval')=='PENDING_REVIEW'
        and component.get('full_q17_qualified') is False)
    evidence=component.get('evidence');require(type(evidence) is list and len(evidence)==6)
    require({r.get('state') for r in evidence}==STATES)
    images=Path(images);files=[]
    for r in evidence:
        require(r.get('schema')=='wam-q17-layout/v1' and r.get('geometry_status')=='PASS'
            and r.get('visual_approval')=='PENDING_REVIEW' and r.get('physical_approval')=='PENDING_OPERATOR'
            and r.get('source_head_sha')==source and r.get('platform')==platform
            and r.get('execution')==('FROZEN' if frozen else 'SOURCE_NATIVE'))
        require(not frozen or r.get('binary_sha256') in binaries)
        require(r.get('qt_platform')=='windows' if platform=='windows-x64' else r.get('qt_platform') in ('cocoa','offscreen','xcb'))
        ratio=r.get('device_pixel_ratio');require(type(ratio) in (int,float) and 0.5<=ratio<=4)
        require(dpr is None or abs(ratio-dpr)<.01)
        records=r.get('records');require(type(records) is list and len(records)==4)
        require({(tuple(row.get('requested',[])),row.get('mode')) for row in records}==
            {((w,h),mode) for w,h in ((820,600),(1280,800)) for mode in ('light','dark')})
        for row in records:
            actual=vector(row.get('actual'),2);require(actual[0]>=820 and actual[1]>=600 and row.get('state')==r['state'])
            controls=row.get('controls');require(type(controls) is list)
            expected={'workspace_title','verification_badge','appearance','refresh_button','status','warning'}
            if r['state']!='verified-spend':expected|={'start_core','stop_core'}
            require(len(controls)==len(expected) and {c.get('name') for c in controls}==expected)
            for c in controls:
                require(inside(c.get('rect'),actual))
                available=vector(c.get('content'),2);needed=vector(c.get('required_text'),2)
                minimum_font={'workspace_title':17,'verification_badge':11,'status':13,'warning':11}.get(c['name'],14)
                require(available[0]>=needed[0] and available[1]>=needed[1] and c.get('font_pixel_size',0)>=minimum_font)
            navigation=row.get('navigation');require(type(navigation) is list and len(navigation)>0)
            expected_nav={'Overview','Receive','History','Send','Security','Settings'} if r['state']=='verified-spend' else {'Overview','Receive','History','Get Started'}
            require({item.get('text') for item in navigation}==expected_nav)
            require(row.get('hidden_navigation')==(['Mining Account'] if r['state']=='verified-spend' else []))
            for item in navigation:
                require(inside(item['rect'],row.get('navigation_viewport')))
                ideal=vector(item['size_hint'],2);require(item['rect'][2]>=ideal[0] and item['rect'][3]>=ideal[1])
            welcome=row.get('welcome_actions');require(type(welcome) is list and len(welcome)==(0 if r['state']=='verified-spend' else 9))
            for c in welcome:
                require(inside(c.get('rect'),actual) and inside(c.get('in_viewport_rect'),c.get('scroll_viewport')))
            name=row.get('screenshot');require(type(name) is str and name.startswith('q17-') and name.endswith('.png') and '/' not in name and '\\' not in name)
            p=images/name;require(p.is_file() and not p.is_symlink() and p.stat().st_size<=8*1024*1024)
            raw=p.read_bytes();require(hashlib.sha256(raw).hexdigest()==row.get('screenshot_sha256') and raw[:8]==b'\x89PNG\r\n\x1a\n')
            width,height=struct.unpack('>II',raw[16:24]);require(abs(width-actual[0]*ratio)<=1 and abs(height-actual[1]*ratio)<=1)
            files.append({'file':name,'sha256':row['screenshot_sha256']})
    return {'geometry_status':'PASS','states':sorted(STATES),'screenshots':files,
        'visual_approval':'PENDING_REVIEW','physical_accepted':False,'full_q17_qualified':False}


def assess_artifacts(root,platform,source,checkout):
    from .a06_artifact_gate import _json,_one,_identity,_payloads
    profiles={'macos-arm64':('native','real-core-evidence.json','frozen','macos-packaged-wallet-evidence.json'),
        'windows-x64':('native','windows-operational-wallet-evidence.json','frozen','windows-packaged-wallet-evidence.json'),
        'linux-x86_64':('native-qt','linux-qt-evidence.json','frozen-desktop','linux-qt-evidence.json')}
    native,name,frozen,report=profiles[platform];record=_json(_one(root/native,name))
    _identity(record['a06_native_source_provenance'],source,checkout)
    rows=[{'role':native,**check_component(record['managed_gui_lifecycle_component'].get('q17_layout_component'),
        root/native/'fusion-ui-review',platform,source,False,dpr=1 if platform=='windows-x64' else None)}]
    mf=_one(root/frozen,'RELEASE_CANDIDATE_MANIFEST.json');manifest=_json(mf);_identity(manifest,source,checkout)
    binaries=_payloads(mf.parent,manifest)
    names=[n for n in manifest['files_sha256'] if n.rsplit('/',1)[-1]==report]
    if len(names)!=(3 if platform=='windows-x64' else 1):raise ValueError('Q17_ALL_FROZEN_VARIANTS_REQUIRED')
    for member in names:
        p=mf.parent/member;record=_json(p)
        images=p.parent/'fusion-ui-review' if platform=='windows-x64' else root/frozen/'fusion-ui-review'
        ratio=1.25 if member.startswith('ui-scale-1.25/') else 1.5 if member.startswith('ui-scale-1.5/') else 1
        rows.append({'role':frozen,'member':member,**check_component(
            record['managed_gui_lifecycle_component'].get('q17_layout_component'),images,platform,source,True,binaries,
            ratio if platform=='windows-x64' else None)})
    return {'status':'PASS','scope':'AUTOMATED_GEOMETRY_ONLY','evidence':rows,
        'visual_approval':'PENDING_REVIEW','physical_accepted':False,'full_q17_qualified':False}
