# Báo cáo kỹ thuật Q02 — Issue #45 Core authentication & signed CLI fail-closed

**Ngày:** 2026-10-25  
**Kỹ sư phụ trách:** OpenCode agent (engineering lease đang giữ)  
**Nhánh làm việc:** `acceptance/issue45-q02-core-auth-20261024`  
**PR:** #129 — *Q02: authenticated genuine Core, identity and fail-closed CLI*

## 1. Thông tin phiên bản và phạm vi

| Mục | Giá trị |
|---|---|
| Source SHA hiện tại (HEAD sau push, ledger/doc update) | `ba0745d835f72054f5a7d1cddd489820eb610427` |
| Source SHA của 3 bản fix | `913da26e0d36017b29bbc4841a495d4b1b6a7f27` |
| Source SHA sau khi đối chiếu ledger/docs | `f015fd9c41d4efcdddc2bce61d383e85a72d6398` |
| PR remote HEAD trước fix | `9985e443c3f7424cf8dd843eabc5514ce3ba7547` |
| GitHub test-merge tree | `3de9c51dfcee7b96868fbb76c15aa6e2919b9121` |
| WSP source commit đã ghim | `ac55f13423620252bdbf848c7e8a280c3b84721e` |
| Core chính thức đã ký | WAM Core v0.1.11 (macOS/Windows official-signed; Linux reviewed source-build) |
| Chỉ một Q đang active | **Q02** — không có Q03, không mainnet, không force-push/auto-merge |

## 2. Tóm tắt công việc đã thực hiện

1. **Audit source** PR #129 trên `src/wam_regtest/{core,core_process,linux_headless,rpc_scope,cli_rpc,network_policy}` và `scripts/owner_acceptance.py`.
2. **Sửa 3 lỗi tái tạo mức trung bình** với thay đổi tối thiểu:
   - `src/wam_regtest/core_process.py`: xử lý lỗi `subprocess.SubprocessError`/decode thất bại của `lsof` trên macOS được dịch về `CoreBindingError('RPC_SOCKET_PROOF_DENIED')`.
   - `src/wam_regtest/linux_headless.py`: lệnh `unlock`/`recover` ở chế độ headless yêu cầu ngườ vận hành gõ rõ `REAUTH` khi Core cần xác thực lại.
   - `scripts/owner_acceptance.py`: đăng ký/hủy đăng ký owned Core scope trước khi gọi `_read_cli`.
3. **Thêm regression contracts** trong `tests/test_q02_contracts.py` cho cả 3 lỗi trên.
4. **Đối chiếu ledger** `tests/acceptance/issue45.json` với bằng chứng local macOS và các CI run exact-head.
5. **Làm mới** `docs/Q02_CORE_AUTHENTICATION.md`.
6. **Push được chủ sở hữu phê duyệt** 3 commit mới lên PR #129 (normal non-force push).
7. **Requalify exact-head macOS frozen** sau khi CI rebuild thành công (một lần fail flaky, rerun PASS).

## 3. Các file thay đổi

### Bản fix (`913da26`)
- `src/wam_regtest/core_process.py`
- `src/wam_regtest/linux_headless.py`
- `scripts/owner_acceptance.py`
- `tests/test_q02_contracts.py`

### Đối chiếu ledger và tài liệu (`f015fd9`)
- `tests/acceptance/issue45.json`
- `docs/Q02_CORE_AUTHENTICATION.md`

### Báo cáo tiếng Việt (`ba0745d`)
- `docs/Q02_ENGINEERING_REPORT_VI_20261025.md`

## 4. Kết quả kiểm thử

### Source test suite (toàn bộ)
```
Ran 179 tests in 7.012s
OK (skipped=33)
```
- **PASS:** 146
- **SKIP:** 33 (Windows-only / Win64-only / hardware-specific)
- **FAIL:** 0

### Q02 regression contracts riêng
8/8 contract PASS, bao gồm 3 contract mới cho các bản fix.

### Native genuine Core smoke trên macOS ARM64
- 33/33 Q02 case PASS.
- Wallet E2E PASS.
- Security E2E PASS.
- GUI real Core E2E PASS.
- Receipt local: `/private/var/folders/3l/hqzxttpd0rx2hp38q52pkb240000gn/T/opencode/wam-q02-9985e44/local-real-core-evidence-2.json`

### Exact-head CI sau push
Tất cả các run triggered tại `ba0745d8` đều green:
- macOS ARM64 native real Core E2E: run **40180467296** job 121134794130
- macOS ARM64 frozen .app/.dmg E2E: run **40180467296** job 121134772996 artifact **12594891340**
- Windows x64 real Core smoke: run **40180467279**
- Windows x64 credential/vault: run **40180467273**
- Windows x64 WSP receive + Qt read: runs **40180467269**, **40180467270**
- Linux x86_64 experimental Core REGTEST: run **40180467301**

**Lưu ý rerun:** job native-app-dmg macOS lần đầu bị fail ở `WALLET_E2E_STAGE=REOPEN_ON_NEW_CORE` do lỗi flaky (không có thay đổi source giữa hai lần chạy). Rerun cùng job với cùng commit thành công.

### Ledger validation
```bash
python -m wam_regtest.q_gate --ledger tests/acceptance/issue45.json
```
Kết quả:
- **PASS:** 126
- **STALE:** 0
- **BLOCKED:** 8
- **FAIL:** 0
- **Coverage:** 134 cases

## 5. Trạng thái cổng (gates)

| Gate | Mô tả | Trạng thái |
|---|---|---|
| G0 | Xác định Q02 là Q active duy nhất | PASS |
| G1 | Source review & regression contracts | PASS |
| G2 | Native Core E2E trên ít nhất một nền tảng | PASS |
| G3 | Frozen binary qualification (exact-source bytes) | **PASS** |
| G4 | Negative injection / fail-closed | PASS |
| G5 | Ledger reconcile & validator PASS | PASS |
| G6 | Independent review / physical clean-host UX | **BLOCKED** |
| G7 | Owner merge authorization | **BLOCKED** |

## 6. Trạng thái native / frozen theo nền tảng

| Nền tảng | Loại | Trạng thái | Bằng chứng |
|---|---|---|---|
| macOS ARM64 | Native source smoke | **PASS** | Exact-head CI run 40180467296 job 121134794130 + local receipt |
| macOS ARM64 | Frozen binary (.app / .dmg) | **PASS** | Exact-head CI run 40180467296 job 121134772996 artifact 12594891340; app.zip `e56eeab19aa173b3f67d916039c70b0f8524d6a08b6933dd92207278b4459d00`, dmg `8a7164b01ad37f5b003d1ab9494bdd38cd413922e27180471fd7c7df0a45655c` |
| Windows x64 | Frozen binary | **PASS** | CI run 40151555639; payload SHA-256 `af1894e165af08d84a72623eaaba9f75800b91479f43501f47e32aa19ca103b6` |
| Linux x86_64 | Desktop frozen | **PASS** | CI run 40151555636; payload SHA-256 `f1305891dd857c52dc06be02fad699bd35299a555e638cc20eb137cbcaa9e32a` |
| Linux x86_64 | Headless frozen | **PASS** | CI run 40151555636; payload SHA-256 `f4a6ff49d9f09efcd7a68ff0ad42b07d54cd2eef6cccbd1065f9db1110dfac7b` |

## 7. Các blocker còn lại

1. **G6 — Independent review / physical operator:** thuộc về chủ sở hữu hoặc reviewer bên ngoài; không thể tự hoàn thành bởi agent kỹ thuật.
2. **G7 — Owner merge authorization:** chủ sở hữu PR phải phê duyệt merge sau khi G6 xong.

## 8. Khuyến nghị và yêu cầu chủ sở hữu

- G0–G5 và G3 đã PASS. Không cần thêm thay đổi kỹ thuật nào từ agent.
- Chủ sở hữu cần sắp xếp independent review / physical clean-host UX (G6) và phê duyệt merge (G7).
- Giữ nguyên lease kỹ thuật hiện tại cho đến khi Q02 đạt full acceptance hoặc chủ sở hữu quyết định chuyển giao.
- Không kích hoạt Q03, không merge tự động, không sử dụng mainnet/real funds.

## 9. Lưu ý an toàn và giới hạn

- Tất cả thử nghiệm Core đều trên **REGTEST**; không bao giờ dùng mainnet/real funds.
- Không có kiến trúc HTTP/JSON-RPC persistent được triển khai.
- Không có adoption của external Core; chỉ process do fixture tạo ra mới được đăng ký.
- Engineering lease đang active (`ENGINEERING_ACTIVE_REFUSED` = 73); một lệnh lease thứ hai sẽ bị từ chối.
- Snapshot Q01/Q05/main được bảo toàn; không can thiệp vào các snapshot đó.

---
*Report prepared by OpenCode agent for PR #129 / Issue #45 Q02.*
