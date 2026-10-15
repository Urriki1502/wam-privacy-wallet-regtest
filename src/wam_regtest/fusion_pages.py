"""Fusion 2.0 reusable screen components; no RPC, keys or signing authority."""
from __future__ import annotations
from PySide6.QtCore import Qt, Signal, QRectF, QTimer
from PySide6.QtGui import QColor,QPainter,QFont,QFontDatabase
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QGridLayout,QLabel,QLineEdit,QComboBox,QCheckBox,QTableWidget,QTableWidgetItem,QHeaderView,QApplication,QDialog,QDialogButtonBox,QFrame
from .fusion_ui import label,panel,page,action,ResponsiveRow,vector_icon,fusion_palette,activity_by_block
from .wallet_read import format_wam


class PaymentQR(QWidget):
    def __init__(self):
        super().__init__();self.matrix=None;self.setMinimumSize(220,220);self.setMaximumSize(300,300);self.setAccessibleName('QR code of the verified REGTEST silent-payment address')
    def set_code(self,code):
        self.matrix=None;self.update()
        if not code:return
        from wam_sp.core import decode_address
        if not code.startswith('wamrtsp1'):raise ValueError('FUSION_RECEIVE_NAMESPACE_DENIED')
        decode_address(code)
        import qrcode
        qr=qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M,border=4,box_size=1)
        qr.add_data(code,optimize=0);qr.make(fit=True);self.matrix=qr.get_matrix();self.update()
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing);r=QRectF(self.rect()).adjusted(1,1,-1,-1);p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor('#FFFFFF'));p.drawRoundedRect(r,12,12)
        if self.matrix:
            n=len(self.matrix);unit=max(1,int(min(self.width()-18,self.height()-18)/n));size=unit*n;left=(self.width()-size)//2;top=(self.height()-size)//2
            p.setRenderHint(QPainter.RenderHint.Antialiasing,False);p.setBrush(QColor('#101010'))
            for y,row in enumerate(self.matrix):
                for x,dark in enumerate(row):
                    if dark:p.drawRect(left+x*unit,top+y*unit,unit,unit)
        else:p.setPen(QColor('#5D6C82'));p.drawText(self.rect(),Qt.AlignmentFlag.AlignCenter,'Address not available\nUnlock and sync the wallet.')
        p.end()


class ReceivePage(QWidget):
    def __init__(self):
        super().__init__();self.code=None;self.setObjectName('FusionInner');root=QVBoxLayout(self);root.setContentsMargins(0,0,0,0)
        self.scroll,layout=page('Receive privately','One genuine BIP352 payment code. A new on-chain destination for each sender.','SILENT PAYMENTS / RECEIVE');root.addWidget(self.scroll)
        card,cl=panel('Your silent-payment address','REGTEST only · send with a compatible BIP352 wallet')
        self.qr=PaymentQR();qrbox=QWidget();ql=QVBoxLayout(qrbox);ql.setContentsMargins(0,0,0,0);ql.addWidget(self.qr,alignment=Qt.AlignmentFlag.AlignCenter);ql.addWidget(label('Exact address QR','FusionKicker'),alignment=Qt.AlignmentFlag.AlignCenter)
        address=QWidget();al=QVBoxLayout(address);al.setContentsMargins(0,0,0,0);al.addWidget(label('BIP352 / REGTEST','FusionBadge'));self.receive_code=label('—','ReceiveCode',True);self.receive_code.setMinimumWidth(0);al.addWidget(self.receive_code)
        self.copy_button=action('Copy full address','copy',True);self.copy_button.setEnabled(False);self.copy_button.clicked.connect(self.copy_address);al.addWidget(self.copy_button);self.copy_status=label('The copied value is never shortened.');al.addWidget(self.copy_status);al.addStretch()
        self._copy_timer=QTimer(self);self._copy_timer.setSingleShot(True)
        self._copy_timer.timeout.connect(lambda:self.copy_status.setText('Copy includes the entire verified address.' if self.code else 'Address unavailable · unlock and verify the chain.'))
        cl.addWidget(ResponsiveRow(qrbox,address,weights=[2,3],breakpoint=610));layout.addWidget(card)
        info,il=panel('A quieter receiving experience');il.addWidget(label('Silent payments avoid publishing a reusable destination on-chain. The wallet scans confirmed blocks using its native WSP-1 account. This is not an anonymity guarantee.'))
        il.addWidget(label('Use disposable REGTEST funds only. Never import a personal production key or send real value.','FusionGold'));layout.addWidget(info)
        self.received=label('No verified receiving activity');layout.addWidget(self.received);layout.addStretch()
    def render_snapshot(self,snap):
        self.code=None;self.copy_button.setEnabled(False);self.receive_code.setText('—');self.qr.set_code(None)
        candidate=snap.receive_code if snap else None;self.qr.set_code(candidate);self.code=candidate;self.receive_code.setText(self.code or '—');self.copy_button.setEnabled(bool(self.code));self.copy_status.setText('Copy includes the entire verified address.' if self.code else 'Address unavailable · unlock and verify the chain.')
        count=sum(r.credit_atoms>0 for r in snap.history) if snap else 0;self.received.setText(f'{count} confirmed transaction(s) with wallet credits' if snap else 'No verified receiving activity')
    def copy_address(self):
        if self.code:
            QApplication.clipboard().setText(self.code);self.copy_status.setText('Full address copied');self._copy_timer.start(2200)


class HistoryPage(QWidget):
    def __init__(self):
        super().__init__();self.setObjectName('FusionInner');self.rows=();self.mode='dark';root=QVBoxLayout(self);root.setContentsMargins(0,0,0,0)
        scroll,layout=page('Transaction history','Explore only the confirmed history verified by WAM Core and WSP-1.','ON-CHAIN / HISTORY');root.addWidget(scroll)
        card,cl=panel();toolbar=QHBoxLayout();self.search=QLineEdit();self.search.setPlaceholderText('Search transaction ID or block height');self.search.setClearButtonEnabled(True);self.search.setAccessibleName('Search confirmed transactions');self.filter=QComboBox();self.filter.addItems(('All activity','Credits','Debits'));toolbar.addWidget(self.search,1);toolbar.addWidget(self.filter);cl.addLayout(toolbar)
        self.table=QTableWidget(0,6);self.table.setObjectName('FusionActivityTable');self.table.setHorizontalHeaderLabels(('DIRECTION','TRANSACTION','BLOCK','CONFIRMED','CREDIT WAM','DEBIT WAM'));self.table.verticalHeader().hide();self.table.setShowGrid(False);self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers);self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows);self.table.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeMode.Stretch);self.table.setMinimumHeight(220);self.table.setColumnWidth(0,110);self.table.setColumnWidth(2,65);self.table.setColumnWidth(3,90);self.table.setColumnWidth(4,145);self.table.setColumnWidth(5,145);cl.addWidget(self.table)
        self.empty=label('No confirmed transactions · unlock and sync to verify history');cl.addWidget(self.empty);layout.addWidget(card)
        detail,dl=panel('Transaction details','Select a row to inspect its exact confirmed data.');self.detail_id=label('No transaction selected','ReceiveCode',True);dl.addWidget(self.detail_id);self.detail_values=label('');dl.addWidget(self.detail_values);self.copy_button=action('Copy full transaction ID','copy');self.copy_button.setEnabled(False);self.copy_button.clicked.connect(self.copy_txid);dl.addWidget(self.copy_button);layout.addWidget(detail);layout.addStretch()
        self.table.itemSelectionChanged.connect(self.show_details);self.search.textChanged.connect(self.apply_filter);self.filter.currentIndexChanged.connect(self.apply_filter)
    def render_snapshot(self,snap):
        self.rows=snap.history if snap else ();self.search.clear();self.table.setRowCount(len(self.rows));self.detail_id.setText('No transaction selected');self.detail_values.setText('');self.copy_button.setEnabled(False)
        c=fusion_palette(self.mode)
        for i,row in enumerate(self.rows):
            net=row.credit_atoms-row.debit_atoms;direction='Received' if net>0 else 'Sent' if net<0 else 'Activity'
            values=(direction,row.txid[:12]+'…',str(row.block_height),str(row.confirmations),format_wam(row.credit_atoms),format_wam(row.debit_atoms))
            for j,value in enumerate(values):
                item=QTableWidgetItem(value);item.setToolTip(row.txid);item.setData(Qt.ItemDataRole.UserRole,row.txid)
                if j==0:item.setIcon(vector_icon('receive' if net>0 else 'send',c['green' if net>0 else 'blue']))
                if j in (1,4,5):item.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
                if j>=2:item.setTextAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(i,j,item)
            self.table.setRowHeight(i,48)
        self.empty.setVisible(not self.rows);self.apply_filter()
    def apply_filter(self,*_):
        term=self.search.text().strip().lower();choice=self.filter.currentIndex();shown=0
        for i,row in enumerate(self.rows):
            visible=(not term or term in row.txid.lower() or term in str(row.block_height)) and (choice==0 or choice==1 and row.credit_atoms>0 or choice==2 and row.debit_atoms>0)
            self.table.setRowHidden(i,not visible);shown+=visible
        self.empty.setVisible(shown==0);self.empty.setText('No matching confirmed transactions' if self.rows else 'No verified transactions · unlock and sync the wallet')
        self.show_details()
    def show_details(self):
        row=self.table.currentRow()
        if not 0<=row<len(self.rows) or self.table.isRowHidden(row):self.detail_id.setText('No transaction selected');self.detail_values.setText('');self.copy_button.setEnabled(False);return
        tx=self.rows[row];self.detail_id.setText(tx.txid);self.detail_values.setText(f'Block {tx.block_height}  /  {tx.confirmations} confirmation(s)\nCredits  {format_wam(tx.credit_atoms)} WAM\nDebits   {format_wam(tx.debit_atoms)} WAM');self.copy_button.setEnabled(True)
    def select_txid(self,txid):
        self.search.clear();self.filter.setCurrentIndex(0)
        for i,tx in enumerate(self.rows):
            if tx.txid==txid:self.table.selectRow(i);self.show_details();return
    def copy_txid(self):
        row=self.table.currentRow()
        if self.copy_button.isEnabled() and 0<=row<len(self.rows):QApplication.clipboard().setText(self.rows[row].txid)


class PaymentSteps(QFrame):
    def __init__(self):
        super().__init__();self.setObjectName('FusionInset');layout=QHBoxLayout(self);layout.setContentsMargins(16,13,16,13);self.labels=[]
        for i,name in enumerate(('Prepare','Review','Approve Sign','Broadcast')):
            item=label(f'{i+1:02d}  {name}','FusionMuted');layout.addWidget(item,1);self.labels.append(item)
    def set_stage(self,stage):
        for i,item in enumerate(self.labels):item.setObjectName('FusionGold' if i==stage else 'FusionMuted');item.style().unpolish(item);item.style().polish(item)


class PaymentApproval(QDialog):
    """UI-only explicit approval, default Cancel; no session operation inside."""
    def __init__(self,review,kind,parent):
        super().__init__(parent);self.setWindowTitle('Approve signature' if kind=='sign' else 'Approve broadcast');self.setObjectName('FusionApproval');self.resize(580,440)
        layout=QVBoxLayout(self);layout.setContentsMargins(28,24,28,24);layout.setSpacing(16)
        layout.addWidget(label('EXPLICIT TRANSACTION APPROVAL','FusionKicker'));layout.addWidget(label('Approve signature' if kind=='sign' else 'Submit to REGTEST','PageTitle'))
        layout.addWidget(label('Signing makes input reservations irreversible.' if kind=='sign' else 'An uncertain broadcast reply retains reservations. Do not assume it failed.','FusionGold'))
        card,cl=panel('Exact recipient');cl.addWidget(label(review.code,'ReceiveCode',True));cl.addWidget(label(f'Amount  {format_wam(review.atoms)} WAM\nFee       {format_wam(review.fee)} WAM\nChange  {format_wam(review.change_atoms)} WAM\nInputs    {review.input_count}'));layout.addWidget(card)
        buttons=QDialogButtonBox();self.cancel=buttons.addButton('Cancel',QDialogButtonBox.ButtonRole.RejectRole);self.approve=buttons.addButton('Approve Sign' if kind=='sign' else 'Approve Broadcast',QDialogButtonBox.ButtonRole.AcceptRole);self.approve.setObjectName('FusionPrimary');self.cancel.setDefault(True);self.approve.setAutoDefault(False);buttons.rejected.connect(self.reject);buttons.accepted.connect(self.accept);layout.addWidget(buttons)
