"""Minimal Vietnamese/English localization for the Q06 BIP39 backup UI.

Uses PySide6's system locale when available; falls back to English. This is a
small scoped dictionary, not a general i18n framework, because no project-wide
localization facility existed before this Q06 UI.
"""
from PySide6.QtCore import QLocale


_STRINGS = {
    "en": {
        "app_name": "WAM Fusion",
        "regtest_preview": "REGTEST PREVIEW",
        "backup_title": "Back up your wallet",
        "backup_subtitle": "Your 12-word recovery phrase is the only way to restore this REGTEST wallet on a new device.",
        "backup_warning": "Never share these words. They control access to your funds. This is a disposable REGTEST wallet — never use mainnet words or real funds.",
        "phrase_grid_title": "Write these 12 words down in order",
        "word_label": "Word",
        "back_up_now": "Back up now",
        "back_up_later": "Back up later",
        "written_checkbox": "I have written these 12 words down in the correct order",
        "verify_title": "Verify your backup",
        "verify_subtitle": "Enter the requested words to confirm you saved the phrase.",
        "verify_prompt": "Enter word #{position}",
        "verify": "Verify",
        "verify_error": "One or more words do not match. Check your written backup and try again.",
        "success_title": "Backup verified",
        "success_subtitle": "Your recovery phrase has been confirmed. You can now use your REGTEST wallet.",
        "continue": "Continue",
        "locked_title": "Wallet locked",
        "locked_subtitle": "Backup was postponed. Reopen this wallet to complete the secure backup.",
        "close_to_lock": "Closing without verifying will lock the wallet. You can complete backup on reopen.",
        "ok": "OK",
        "cancel": "Cancel",
    },
    "vi": {
        "app_name": "WAM Fusion",
        "regtest_preview": "BẢN XEM TRƯỚC REGTEST",
        "backup_title": "Sao lưu ví của bạn",
        "backup_subtitle": "Cụm 12 từ khôi phục là cách duy nhất để khôi phục ví REGTEST này trên thiết bị mới.",
        "backup_warning": "Không bao giờ chia sẻ các từ này. Chúng kiểm soát quyền truy cập vào tiền của bạn. Đây là ví REGTEST dùng một lần — không bao giờ dùng từ mainnet hay tiền thật.",
        "phrase_grid_title": "Viết đúng 12 từ này theo thứ tự",
        "word_label": "Từ",
        "back_up_now": "Sao lưu ngay",
        "back_up_later": "Sao lưu sau",
        "written_checkbox": "Tôi đã viết đúng 12 từ này theo đúng thứ tự",
        "verify_title": "Xác minh bản sao lưu",
        "verify_subtitle": "Nhập các từ được yêu cầu để xác nhận bạn đã lưu cụm khôi phục.",
        "verify_prompt": "Nhập từ thứ {position}",
        "verify": "Xác minh",
        "verify_error": "Một hoặc nhiều từ không khớp. Kiểm tra bản sao lưu đã viết và thử lại.",
        "success_title": "Đã xác minh sao lưu",
        "success_subtitle": "Cụm khôi phục của bạn đã được xác nhận. Bạn có thể sử dụng ví REGTEST ngay bây giờ.",
        "continue": "Tiếp tục",
        "locked_title": "Ví đã khóa",
        "locked_subtitle": "Việc sao lưu đã bị hoãn. Hãy mở lại ví để hoàn tất sao lưu an toàn.",
        "close_to_lock": "Đóng mà không xác minh sẽ khóa ví. Bạn có thể hoàn tất sao lưu khi mở lại.",
        "ok": "OK",
        "cancel": "Hủy",
    },
}


def _lang():
    name = QLocale.system().name().lower()
    return "vi" if name.startswith("vi") else "en"


def t(key):
    """Return the localized string for `key`, falling back to English."""
    return _STRINGS[_lang()].get(key, _STRINGS["en"].get(key, key))
