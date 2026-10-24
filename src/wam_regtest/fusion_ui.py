"""Fusion 2.0 shared Qt presentation: verified snapshots, never wallet authority."""
from __future__ import annotations

from PySide6.QtCore import Qt, QRect, QRectF, QPointF, QSize, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QIcon, QPixmap, QPolygonF, QLinearGradient, QPainterPath, QFont, QFontMetrics
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget, QToolTip, QSizePolicy, QTableWidget, QTableWidgetItem, QPlainTextEdit
from .wallet_read import WalletReadSnapshot, format_wam
from .branding import brand_image

SPACING = (4, 8, 12, 16, 24, 32)
TYPE = {'display':42, 'heading':26, 'section':17, 'body':14, 'caption':12}


def fusion_palette(mode):
    if mode=='dark':
        return dict(bg='#0B1018',surface='#192333',panel='#111925',text='#F5F6F8',muted='#A7B6C8',border='#2A3648',
            tint='#202D40',accent='#F1C55A',onaccent='#211A09',warning='#352A18',warning_text='#F7D78A',
            green='#61D7B1',blue='#8BB8FF',red='#FF9A9A',hero_bottom='#152035',selection='#322D20',
            grid='#2B384C',chart_empty='#A7B6C8',hover='#26364C',sidebar='#111925',success='#61D7B1',
            pending='#F1C55A',error='#FF9A9A',focus='#F1C55A',shadow='#070C13')
    if mode=='light':
        return dict(bg='#F4F6FA',surface='#FFFFFF',panel='#EAF0F6',text='#172436',muted='#5D6C82',border='#D7E0EA',
            tint='#EAF0F6',accent='#795507',onaccent='#FFFFFF',warning='#FFF1D4',warning_text='#694710',
            green='#116F53',blue='#285EAD',red='#B3374B',hero_bottom='#FFF9EA',selection='#F8EDD2',
            grid='#DFE6EE',chart_empty='#5D6C82',hover='#E2EAF3',sidebar='#FFFFFF',success='#116F53',
            pending='#795507',error='#B3374B',focus='#795507',shadow='#E3E8F0')
    raise ValueError('FUSION_THEME_DENIED')


def fusion_stylesheet(mode):
    c=fusion_palette(mode)
    return f"""
    QMainWindow,QWidget#WalletRoot {{background:{c['bg']};color:{c['text']};}}
    QWidget {{font-size:14px;}}
    QFrame#FusionSidebar {{background:{c['sidebar']};border-right:1px solid {c['border']};}}
    QFrame#FusionTopbar {{background:{c['bg']};border-bottom:1px solid {c['border']};}}
    QFrame#FusionPanel,QFrame#ContentCard,QFrame#HeaderCard {{background:{c['surface']};border:1px solid {c['border']};border-radius:16px;}}
    QFrame#FusionInset {{background:{c['panel']};border:1px solid {c['border']};border-radius:12px;}}
    QFrame#FusionHero {{background:transparent;}}
    QWidget#FusionInner,QScrollArea#FusionScroll,QWidget#FusionTransparent {{background:transparent;border:0;}}
    QLabel {{color:{c['text']};background:transparent;border:0;}}
    QLabel#BrandTitle {{font-size:24px;font-weight:700;letter-spacing:1px;}}
    QLabel#PageTitle {{font-size:26px;font-weight:700;}}
    QLabel#FusionBalance,QLabel#BalanceValue {{font-size:42px;font-weight:600;color:{c['text']};}}
    QLabel#FusionKicker {{font-size:12px;font-weight:600;color:{c['muted']};letter-spacing:1px;}}
    QLabel#FusionCardTitle {{font-size:17px;font-weight:600;}}
    QLabel#FusionCardValue {{font-size:21px;font-weight:600;}}
    QLabel#FusionMuted,QLabel#SecondaryLabel,QLabel#StatusText,QLabel#FusionEmpty {{color:{c['muted']};font-size:13px;}}
    QLabel#FusionVerified {{color:{c['green']};font-weight:600;}}
    QLabel#FusionInfo {{color:{c['blue']};}}
    QLabel#FusionGold {{color:{c['accent']};font-weight:600;}}
    QLabel#FusionBadge {{color:{c['accent']};background:{c['selection']};border:1px solid {c['border']};border-radius:8px;padding:5px 9px;font-size:11px;font-weight:600;}}
    QLabel#Warning {{color:{c['warning_text']};background:{c['warning']};border-radius:9px;padding:10px;min-height:64px;font-size:11px;}}
    QLabel#ReceiveCode,QPlainTextEdit#ReceiveCode {{font-size:14px;background:{c['panel']};border:1px solid {c['border']};border-radius:12px;padding:16px;}}
    QListWidget {{background:transparent;color:{c['muted']};border:0;padding:4px;font-size:14px;}}
    QListWidget::item {{padding:14px 12px;border-radius:10px;margin:3px 0;}}
    QListWidget::item:selected {{background:{c['selection']};color:{c['accent']};font-weight:600;}}
    QListWidget::item:hover:!selected {{background:{c['tint']};color:{c['text']};}}
    QLineEdit,QTextEdit,QPlainTextEdit {{background:{c['panel']};color:{c['text']};selection-background-color:{c['selection']};border:1px solid {c['border']};border-radius:10px;padding:12px;}}
    QLineEdit:focus,QPushButton:focus,QComboBox:focus {{border:2px solid {c['focus']};}}
    QLineEdit:disabled {{color:{c['muted']};background:{c['bg']};}}
    QPushButton,QComboBox {{background:{c['tint']};color:{c['text']};border:1px solid {c['border']};border-radius:9px;padding:11px 14px;font-weight:600;}}
    QPushButton#PrimaryButton,QPushButton#FusionPrimary {{background:{c['accent']};color:{c['onaccent']};border:1px solid {c['accent']};}}
    QPushButton#FusionSecondary {{background:{c['surface']};color:{c['accent']};border:1px solid {c['accent']};}}
    QPushButton#FusionDestructive {{background:{c['surface']};color:{c['red']};border:1px solid {c['border']};}}
    QPushButton:hover:enabled,QComboBox:hover {{background:{c['hover']};border:1px solid {c['accent']};}}
    QPushButton#FusionPrimary:hover:enabled,QPushButton#PrimaryButton:hover:enabled {{background:{c['accent']};border:1px solid {c['onaccent']};}}
    QPushButton:pressed:enabled {{background:{c['selection']};}}
    QPushButton#FusionPrimary:disabled,QPushButton#PrimaryButton:disabled,QPushButton#FusionSecondary:disabled,QPushButton#FusionDestructive:disabled,QPushButton:disabled {{background:{c['panel']};color:{c['muted']};border:1px solid {c['border']};}}
    QComboBox::drop-down {{border:0;width:22px;}}
    QComboBox QAbstractItemView {{background:{c['surface']};color:{c['text']};selection-background-color:{c['selection']};border:1px solid {c['border']};}}
    QCheckBox {{color:{c['text']};spacing:8px;}}
    QCheckBox::indicator {{width:17px;height:17px;border:1px solid {c['muted']};border-radius:4px;background:{c['panel']};}}
    QCheckBox::indicator:checked {{background:{c['accent']};border:1px solid {c['accent']};}}
    QTableWidget,QTableWidget#FusionActivityTable {{background:{c['surface']};alternate-background-color:{c['surface']};color:{c['text']};border:0;gridline-color:{c['border']};selection-background-color:{c['selection']};selection-color:{c['text']};}}
    QTableWidget::item {{padding:10px;border-bottom:1px solid {c['border']};}}
    QTableWidget::item:selected {{background:{c['selection']};color:{c['text']};}}
    QHeaderView::section {{background:{c['surface']};color:{c['muted']};border:0;border-bottom:1px solid {c['border']};padding:10px;font-size:12px;font-weight:600;}}
    QScrollBar:vertical {{background:transparent;width:7px;}} QScrollBar::handle:vertical {{background:{c['border']};border-radius:3px;min-height:30px;}}
    QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {{height:0;}} QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical {{background:transparent;}}
    QToolTip {{background:{c['surface']};color:{c['text']};border:1px solid {c['border']};padding:8px;}}
    QDialog,QMessageBox,QInputDialog {{background:{c['bg']};color:{c['text']};}}
    """


class ReadableText(QPlainTextEdit):
    """Selectable exact plaintext with genuine wrap-anywhere; no hidden characters."""
    def __init__(self,text=''):
        super().__init__()
        from PySide6.QtGui import QTextOption,QFontDatabase
        self.setReadOnly(True);self.setWordWrapMode(QTextOption.WrapMode.WrapAnywhere)
        families=set(QFontDatabase.families())
        family=next((f for f in ('Menlo','Consolas','Courier New') if f in families),None)
        self.setFont(QFont(family,10) if family else QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(0);self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setPlainText(text);self._fit()
    def text(self):return self.toPlainText()
    def setText(self,text):
        if text!=self.toPlainText():self.setPlainText(text)
        self._fit()
    def _fit(self):
        import math
        fm=self.fontMetrics();width=max(80,self.viewport().width()-28)
        lines=sum(max(1,math.ceil(fm.horizontalAdvance(line)/width)) for line in self.toPlainText().split('\n'))
        self.setFixedHeight(min(340,max(100,lines*fm.lineSpacing()+64)))
    def resizeEvent(self,event):super().resizeEvent(event);self._fit()
    def minimumSizeHint(self):return QSize(0,68)


class ActionFlowLayout(QLayout):
    """Keep natural control sizes; wrap rows before text must be compressed.

    Qt height-for-width lets the workspace reserve the complete toolbar height.
    Hidden delegated actions retain their handlers but occupy no layout space.
    """
    def __init__(self, parent):
        super().__init__(parent)
        self._items=[]
        self.setSpacing(8)

    def addItem(self,item):
        self._items.append(item)
        self.invalidate()

    def count(self): return len(self._items)
    def itemAt(self,index): return self._items[index] if 0<=index<len(self._items) else None
    def takeAt(self,index):
        if 0<=index<len(self._items):
            item=self._items.pop(index);self.invalidate();return item
        return None
    def expandingDirections(self): return Qt.Orientation.Horizontal
    def hasHeightForWidth(self): return True
    def sizeHint(self): return self.minimumSize()

    def minimumSize(self):
        result=QSize(0,0)
        for item in self._items:
            if not item.isEmpty(): result=result.expandedTo(item.sizeHint().expandedTo(item.minimumSize()))
        m=self.contentsMargins()
        return result+QSize(m.left()+m.right(),m.top()+m.bottom())

    def _rows(self,width):
        rows=[];row=[];used=0
        for item in self._items:
            if item.isEmpty(): continue
            size=item.sizeHint().expandedTo(item.minimumSize())
            needed=size.width()+(self.spacing() if row else 0)
            if row and used+needed>width:
                rows.append(row);row=[];used=0;needed=size.width()
            row.append((item,size));used+=needed
        if row: rows.append(row)
        return rows

    def heightForWidth(self,width):
        m=self.contentsMargins();rows=self._rows(max(1,width-m.left()-m.right()))
        return m.top()+m.bottom()+sum(max(s.height() for _,s in row) for row in rows)+max(0,len(rows)-1)*self.spacing()

    def setGeometry(self,rect):
        super().setGeometry(rect)
        m=self.contentsMargins();width=max(1,rect.width()-m.left()-m.right());y=rect.y()+m.top()
        for row in self._rows(width):
            height=max(s.height() for _,s in row);x=rect.x()+m.left()
            slack=max(0,width-sum(s.width() for _,s in row)-(len(row)-1)*self.spacing())
            for item,size in row:
                w=size.width()
                if item.widget().property('fusion_toolbar_title'): w+=slack
                item.setGeometry(QRect(x,y+(height-size.height())//2,w,size.height()))
                x+=w+self.spacing()
            y+=height+self.spacing()


def label(text='',role='FusionMuted',selectable=False):
    if role=='ReceiveCode':
        obj=ReadableText(text);obj.setObjectName(role);return obj
    obj=QLabel(text);obj.setObjectName(role);obj.setWordWrap(role not in ('FusionKicker','FusionBadge'));obj.setSizePolicy(QSizePolicy.Policy.Preferred,QSizePolicy.Policy.Maximum)
    if role=='FusionBadge':obj.setFixedHeight(28);obj.setSizePolicy(QSizePolicy.Policy.Maximum,QSizePolicy.Policy.Fixed)
    if selectable:obj.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return obj


def panel(title=None,subtitle=None,*,inset=False):
    obj=QFrame();obj.setObjectName('FusionInset' if inset else 'FusionPanel')
    layout=QVBoxLayout(obj);layout.setContentsMargins(22,20,22,20);layout.setSpacing(12);layout.setAlignment(Qt.AlignmentFlag.AlignTop)
    if title:layout.addWidget(label(title,'FusionCardTitle'))
    if subtitle:layout.addWidget(label(subtitle))
    return obj,layout


def page(title,subtitle,kicker='WAM FUSION / REGTEST'):
    scroll=QScrollArea();scroll.setObjectName('FusionScroll');scroll.setFrameShape(QFrame.Shape.NoFrame);scroll.setWidgetResizable(True)
    root=QWidget();root.setObjectName('FusionInner');scroll.setWidget(root)
    layout=QVBoxLayout(root);layout.setContentsMargins(4,4,12,16);layout.setSpacing(20)
    layout.addWidget(label(kicker,'FusionKicker'));layout.addWidget(label(title,'PageTitle'));layout.addWidget(label(subtitle))
    return scroll,layout


def action(text,icon,primary=False):
    button=QPushButton(text);button.setProperty('fusion_icon',icon)
    button.setObjectName('FusionPrimary' if primary else 'FusionSecondary')
    button.setIconSize(QSize(18,18));return button


_NAMES=('overview','receive','history','send','security','settings')
def vector_icon(name,tone,dpr=2):
    """One original outline geometry family, rasterized at device resolution."""
    color=QColor(tone)
    if not color.isValid():raise ValueError('FUSION_ICON_COLOR_DENIED')
    pix=QPixmap(int(24*dpr),int(24*dpr));pix.setDevicePixelRatio(dpr);pix.fill(Qt.GlobalColor.transparent)
    p=QPainter(pix);p.setRenderHint(QPainter.RenderHint.Antialiasing);p.setPen(QPen(color,1.65,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap,Qt.PenJoinStyle.RoundJoin));p.setBrush(Qt.BrushStyle.NoBrush)
    def line(a,b,c,d):p.drawLine(QPointF(a,b),QPointF(c,d))
    if name=='overview':
        for x,y,w,h in ((3,3,7,7),(14,3,7,7),(3,14,7,7),(14,14,7,7)):p.drawRoundedRect(QRectF(x,y,w,h),1.5,1.5)
    elif name in ('receive','send'):
        if name=='receive':line(12,3,12,16);line(7,11,12,16);line(17,11,12,16);line(4,20,20,20)
        else:p.drawPolygon(QPolygonF([QPointF(3,10),QPointF(21,3),QPointF(14,21),QPointF(10,14)]));line(10,14,21,3)
    elif name=='history':p.drawEllipse(QRectF(4,4,16,16));line(12,7,12,12);line(12,12,16,14)
    elif name in ('security','anchor'):
        p.drawPolygon(QPolygonF([QPointF(12,3),QPointF(20,7),QPointF(19,16),QPointF(12,21),QPointF(5,16),QPointF(4,7)]));line(8,12,11,15);line(11,15,16,9)
    elif name=='settings':
        p.drawEllipse(QRectF(6,6,12,12));p.drawEllipse(QRectF(10,10,4,4))
        for a,b,c,d in ((12,2,12,5),(12,19,12,22),(2,12,5,12),(19,12,22,12),(4,4,6,6),(18,18,20,20),(4,20,6,18),(18,6,20,4)):line(a,b,c,d)
    elif name=='copy':p.drawRoundedRect(QRectF(8,8,12,13),2,2);line(4,16,4,3);line(4,3,16,3)
    elif name in ('lock','unlock'):p.drawRoundedRect(QRectF(5,10,14,11),2,2);p.drawArc(QRectF(8,3,8,12),0 if name=='lock' else 20*16,180*16);line(12,14,12,17)
    elif name=='backup':p.drawRoundedRect(QRectF(4,4,16,17),2,2);line(8,4,8,10);line(8,10,16,10);line(16,10,16,4);p.drawRect(QRectF(8,15,8,6))
    elif name=='sync':p.drawArc(QRectF(4,4,16,16),35*16,260*16);line(19,3,20,9);line(20,9,14,8)
    elif name=='core':p.drawRoundedRect(QRectF(6,6,12,12),2,2);p.drawRect(QRectF(10,10,4,4));
    elif name=='check':line(5,12,10,17);line(10,17,20,6)
    else:p.drawEllipse(QRectF(5,5,14,14));line(12,7,12,17);line(7,12,17,12)
    p.end();return QIcon(pix)


def fusion_nav_icons(tone):return tuple(vector_icon(n,tone) for n in _NAMES)


def activity_by_block(snapshot):
    if snapshot is None:return ()
    if type(snapshot) is not WalletReadSnapshot or snapshot.synthetic_rpc or snapshot.chain!='regtest' or snapshot.mainnet_allowed:
        raise ValueError('FUSION_HISTORY_UNVERIFIED_DENIED')
    blocks={}
    for row in snapshot.history:
        if (type(row.block_height) is not int or not 1<=row.block_height<=snapshot.height or type(row.confirmations) is not int or row.confirmations<=0 or type(row.credit_atoms) is not int or row.credit_atoms<0 or type(row.debit_atoms) is not int or row.debit_atoms<0):
            raise ValueError('FUSION_HISTORY_UNVERIFIED_DENIED')
        agg=blocks.setdefault(row.block_height,[0,0]);agg[0]+=row.credit_atoms;agg[1]+=row.debit_atoms
    return tuple((h,*blocks[h]) for h in sorted(blocks)[-14:])


class ResponsiveRow(QWidget):
    def __init__(self,*children,weights=None,breakpoint=760):
        super().__init__();self.setObjectName('FusionTransparent');self._break=breakpoint;self._children=children;self._weights=weights or [1]*len(children);self._vertical=None
        self._grid=QGridLayout(self);self._grid.setContentsMargins(0,0,0,0);self._grid.setSpacing(18)
        # Establish native ownership immediately, including never-shown windows.
        # Waiting for resizeEvent leaves whole panels as independent top-level
        # widgets. PySide's application cleanup can then destroy their children
        # before their parents, revisiting stale native pointers at shutdown.
        self._arrange()
    def _arrange(self):
        vertical=self.width()<self._break
        if vertical!=self._vertical:
            self._vertical=vertical
            for i,child in enumerate(self._children):self._grid.addWidget(child,i if vertical else 0,0 if vertical else i)
            for i,w in enumerate(self._weights):self._grid.setColumnStretch(i,0 if vertical else w)
    def resizeEvent(self,event):
        self._arrange()
        super().resizeEvent(event)


class Hero(QFrame):
    def __init__(self):
        super().__init__();self.setObjectName('FusionHero');self.mode='dark';self.logo=QPixmap(str(brand_image()));self.setMinimumHeight(184)
    def paintEvent(self,event):
        c=fusion_palette(self.mode);p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect=QRectF(self.rect()).adjusted(1,1,-1,-1);path=QPainterPath();path.addRoundedRect(rect,18,18);p.setClipPath(path)
        gradient=QLinearGradient(rect.topLeft(),rect.bottomRight());gradient.setColorAt(0,QColor(c['surface']));gradient.setColorAt(1,QColor(c['hero_bottom']))
        p.fillPath(path,gradient);p.setOpacity(.09 if self.mode=='dark' else .045);p.drawPixmap(self.width()-225,4,220,220,self.logo)
        p.setOpacity(.1);p.setPen(QPen(QColor(c['accent']),1))
        for offset in (0,16,32):p.drawLine(QPointF(self.width()-280+offset,0),QPointF(self.width()-180+offset,self.height()))
        p.setOpacity(.65);p.setClipping(False);p.setPen(QPen(QColor(c['border']),1));p.drawRoundedRect(rect,18,18);p.end()


class ChainActivity(QWidget):
    """Gross confirmed credits/debits: discrete block columns, exact hover data."""
    def __init__(self):
        super().__init__();self._activity=();self._mode='dark';self._hit=[];self._hover=-1;self.setMinimumHeight(196);self.setMouseTracking(True);self.setAccessibleName('Confirmed on-chain credit and debit activity')
    def render_snapshot(self,snapshot):
        self._activity=activity_by_block(snapshot);self._hover=-1;self._hit=[];QToolTip.hideText();self.update()
    def set_theme(self,mode):fusion_palette(mode);self._mode=mode;self.update()
    def mouseMoveEvent(self,event):
        index=next((i for i,r in enumerate(self._hit) if r.contains(event.position())),-1)
        if index!=self._hover:self._hover=index;self.update()
        if index>=0:
            h,credit,debit=self._activity[index]
            QToolTip.showText(event.globalPosition().toPoint(),f'Confirmed block {h}\nCredits  {format_wam(credit)} WAM\nDebits   {format_wam(debit)} WAM',self)
        else:QToolTip.hideText()
    def leaveEvent(self,event):self._hover=-1;QToolTip.hideText();self.update()
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing);c=fusion_palette(self._mode);p.setFont(QFont(p.font().family(),10))
        if not self._activity:
            p.setPen(QColor(c['chart_empty']));p.drawText(self.rect(),Qt.AlignmentFlag.AlignCenter,'No confirmed activity\nSync the verified chain to see credits and debits.');p.end();return
        left,top,right,bottom=66.,20.,self.width()-16.,self.height()-37.
        maximum=max(max(a,b) for _,a,b in self._activity)
        if maximum<=0:p.end();return
        quantum=10**max(0,len(str(maximum))-1);ceiling=((maximum+quantum-1)//quantum)*quantum
        for j in range(5):
            value=ceiling*j//4;y=bottom-(bottom-top)*j/4
            p.setPen(QPen(QColor(c['grid']),1,Qt.PenStyle.DotLine));p.drawLine(QPointF(left,y),QPointF(right,y))
            p.setPen(QColor(c['muted']));amount=format_wam(value).rstrip('0').rstrip('.')
            p.drawText(QRectF(0,y-8,left-12,18),Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter,amount)
        count=len(self._activity);span=(right-left)/count;width=min(22.,span*.21);self._hit=[]
        for i,(height,credit,debit) in enumerate(self._activity):
            center=left+span*(i+.5);hit=QRectF(left+i*span,top,span,bottom-top);self._hit.append(hit)
            if i==self._hover:p.fillRect(hit,QColor(c['panel']))
            for x,atoms,color in ((center-width*.62,credit,c['accent']),(center+width*.62,debit,c['blue'])):
                if atoms<=0:continue
                bh=(bottom-top)*atoms/ceiling;r=QRectF(x-width/2,bottom-bh,width,bh)
                gradient=QLinearGradient(r.topLeft(),r.bottomLeft());gradient.setColorAt(0,QColor(color));faded=QColor(color);faded.setAlpha(75);gradient.setColorAt(1,faded)
                p.setPen(Qt.PenStyle.NoPen);p.setBrush(gradient);p.drawRoundedRect(r,4,4);p.setBrush(QColor(color));p.drawEllipse(QPointF(x,bottom-bh),3,3)
            p.setPen(QColor(c['muted']))
            if count<9 or i%2==0:p.drawText(QRectF(center-span/2,bottom+9,span,20),Qt.AlignmentFlag.AlignHCenter,str(height))
        p.end()


class FusionOverview(QScrollArea):
    transaction_selected=Signal(str)
    def __init__(self):
        super().__init__();self.setObjectName('FusionScroll');self.setFrameShape(QFrame.Shape.NoFrame);self.setWidgetResizable(True)
        root=QWidget();root.setObjectName('FusionInner');self.setWidget(root);whole=QVBoxLayout(root);whole.setContentsMargins(4,4,12,16);whole.setSpacing(14)
        head=QHBoxLayout();titles=QVBoxLayout();titles.addWidget(label('YOUR WALLET / REGTEST','FusionKicker'));titles.addWidget(label('Overview','PageTitle'));head.addLayout(titles);head.addStretch();self.live_badge=label('Awaiting verification','FusionBadge');head.addWidget(self.live_badge);whole.addLayout(head)
        self.hero=Hero();hero=QVBoxLayout(self.hero);hero.setContentsMargins(24,20,24,20);hero.setSpacing(10)
        hero.addWidget(label('CONFIRMED BALANCE','FusionKicker'));self.balance_value=label('—','FusionBalance',True);hero.addWidget(self.balance_value)
        self.utxo_details=label('Awaiting verified Core / WSP state');hero.addWidget(self.utxo_details)
        row=QHBoxLayout();self.go_receive=action('Receive','receive',True);self.go_send=action('Send payment','send');self.go_send.setEnabled(False);row.addWidget(self.go_receive);row.addWidget(self.go_send);row.addStretch();hero.addLayout(row)
        privacy,pl=panel('Silent payments','BIP352 destinations · native WSP-1 scanning')
        pl.setContentsMargins(20,16,20,16);pl.setSpacing(8)
        self.security_note=label('Experimental REGTEST custody.\nNo production or anonymity guarantee.');pl.addWidget(self.security_note)
        self.open_security=action('Security & backup','security');self.open_security.setEnabled(False);pl.addWidget(self.open_security);pl.addStretch()
        whole.addWidget(ResponsiveRow(self.hero,privacy,weights=[3,2]))
        self.status_cards=[];self.status_icons=[];cards=[]
        for name,caption,icon in (('Verified Core','Pinned binary identity','core'),('WSP-1 scanner','BIP352 · live SQLite checkpoint','sync'),('Wallet custody','Native checkpoint anchor','security')):
            card,cl=panel();top=QHBoxLayout();icon_label=QLabel();icon_label.setProperty('fusion_icon_label',icon);icon_label.setFixedSize(24,24);top.addWidget(icon_label);top.addWidget(label(name,'FusionCardTitle'));top.addStretch();cl.addLayout(top)
            cl.setContentsMargins(18,14,18,14);cl.setSpacing(7)
            value=label('Not verified','FusionCardValue');cl.addWidget(value);cl.addWidget(label(caption));self.status_cards.append(value);self.status_icons.append(icon_label);cards.append(card)
        self.core_status,self.scanner_status,self.vault_status=self.status_cards;whole.addWidget(ResponsiveRow(*cards,breakpoint=650))
        chart_card,chart=panel('Confirmed on-chain activity','Gross credits / debits, including change. Not balance history or market price.')
        legend=QHBoxLayout();legend.addWidget(label('Credits · WAM','FusionGold'));legend.addWidget(label('Debits · WAM','FusionInfo'));legend.addStretch();legend.addWidget(label('Confirmed block','FusionMuted'));chart.addLayout(legend);self.chart=ChainActivity();chart.addWidget(self.chart);
        activity,al=panel();top=QHBoxLayout();top.addWidget(label('Recent transactions','FusionCardTitle'));top.addStretch();self.open_history=action('View history','history');top.addWidget(self.open_history);al.addLayout(top)
        self.activity_table=QTableWidget(0,2);self.activity_table.setObjectName('FusionActivityTable');self.activity_table.setHorizontalHeaderLabels(('ACTIVITY','NET WAM'));self.activity_table.verticalHeader().hide();self.activity_table.setShowGrid(False);self.activity_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers);self.activity_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows);self.activity_table.horizontalHeader().setStretchLastSection(True);self.activity_table.setMinimumHeight(196);self.activity_table.setColumnWidth(0,158);self.activity_table.cellClicked.connect(self._select_tx)
        self._txids=[];al.addWidget(self.activity_table);self.empty=label('No confirmed transactions yet. Your verified on-chain activity will appear here.');al.addWidget(self.empty);whole.addWidget(ResponsiveRow(chart_card,activity,weights=[3,2],breakpoint=820))
        bottom=QHBoxLayout();self.evidence_text=label('No verified blockchain snapshot');bottom.addWidget(self.evidence_text,1);self.manual_sync=action('Sync chain','sync');bottom.addWidget(self.manual_sync);whole.addLayout(bottom)
    def _select_tx(self,row,column):
        if 0<=row<len(self._txids):self.transaction_selected.emit(self._txids[row])
    def set_theme(self,mode):
        self.hero.mode=mode;self.hero.update();self.chart.set_theme(mode)
        for row in range(self.activity_table.rowCount()):
            item=self.activity_table.item(row,0)
            if item is not None:
                positive=item.data(Qt.ItemDataRole.UserRole)>0
                item.setIcon(vector_icon('receive' if positive else 'send',fusion_palette(mode)['green' if positive else 'blue']))
    def render_snapshot(self,snap,*,locked=False,operational=False):
        if snap is None or locked:
            self.balance_value.setText('—');self.utxo_details.setText('Unlock and verify the chain to display wallet values.');self.live_badge.setText('Locked / not verified' if locked else 'Not verified')
            for value in self.status_cards:value.setText('Not verified')
            self.vault_status.setText('Locked' if locked else 'Not attested');self.evidence_text.setText('No verified blockchain snapshot');self.evidence_text.setToolTip('');self.activity_table.setRowCount(0);self._txids=[];self.empty.show();self.chart.render_snapshot(None);self.go_receive.setEnabled(False);return
        activity_by_block(snap)
        self.balance_value.setText(format_wam(snap.confirmed_atoms,grouped=True)+' WAM');self.utxo_details.setText(f'{snap.confirmed_utxos} confirmed UTXO(s)  /  Verified block {snap.height}')
        self.live_badge.setText('REGTEST VERIFIED');self.core_status.setText('Identity verified');self.scanner_status.setText(f'Synced · {snap.height}');self.vault_status.setText('Unlocked test wallet' if operational else 'Read-only account');self.go_receive.setEnabled(True)
        self.evidence_text.setText('Verified tip '+snap.tip[:14]+'…  /  No real funds');self.evidence_text.setToolTip('Core SHA-256: '+snap.core_sha256+'\nVerified tip: '+snap.tip);self.chart.render_snapshot(snap)
        rows=snap.history[:4];self._txids=[r.txid for r in rows];self.activity_table.setRowCount(len(rows));self.empty.setVisible(not rows)
        for i,tx in enumerate(rows):
            value=tx.credit_atoms-tx.debit_atoms;direction='Received' if value>0 else 'Sent' if value<0 else 'Activity'
            for j,text in enumerate((direction+' · '+str(tx.block_height)+'\nConfirmed ('+str(tx.confirmations)+')',('+' if value>0 else '-' if value<0 else '')+format_wam(abs(value)))):
                item=QTableWidgetItem(text);item.setToolTip(tx.txid+'\nClick to view exact transaction details')
                if j==0:
                    item.setData(Qt.ItemDataRole.UserRole,value)
                    item.setIcon(vector_icon('receive' if value>0 else 'send',fusion_palette(self.chart._mode)['green' if value>0 else 'blue']))
                if j==1:item.setTextAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter)
                self.activity_table.setItem(i,j,item)
            self.activity_table.setRowHeight(i,60)
