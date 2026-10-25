# Báo cáo kỹ thuật Q02 — Issue #45 Core authentication & signed CLI fail-closed

**Ngày:** 2026-10-25  
**Kỹ sư phụ trách:** OpenCode agent (engineering lease đang giữ)  
**Nhánh làm việc:** `acceptance/issue45-q02-core-auth-20261024`  
**PR:** #129 — *Q02: authenticated genuine Core, identity and fail-closed CLI*

## 1. Thông tin phiên bản và phạm vi

| Mục | Giá trị |
|---|---|
| Source SHA đang review (HEAD hiện tại) | `43d94c173c5728e7f96579820e4985af5c6bc97e` |
| Source SHA sau bản fix F1 (chưa push) | *sẽ được tính sau khi commit* |
| Source SHA của 3 bản fix trước đó | `913da26e0d36017b29bbc4841a495d4b1b6a7f27` |
| Source SHA sau đối chiếu ledger/docs lần 1 | `f015fd9c41d4efcdddc2bce61d383e85a72d6398` |
| Source SHA sau push và báo cáo lần 1 | `ba0745d835f72054f5a7d1cddd489820eb610427` |
| Source SHA exact-head green trước fix F1 | `f669152fca09bc06d2b477e04ded4ac3e14c7436` |
| PR remote HEAD trước fix | `9985e443c3f7424cf8dd843eabc5514ce3ba7547` |
| GitHub test-merge tree | `3de9c51dfcee7b96868fbb76c15aa6e2919b9121` |
| WSP source commit đã ghim | `ac55f13423620252bdbf848c7e8a280c3b84721e` |
| Core chính thức đã ký | WAM Core v0.1.11 (macOS/Windows official-signed; Linux reviewed source-build) |
| Chỉ một Q đang active | **Q02** — không có Q03, không mainnet, không force-push/auto-merge |

## 2. Tóm tắt công việc đã thực hiện

1. **Audit source** PR #129 trên `src/wam_regtest/{core,core_process,linux_headless,rpc_scope,cli_rpc,network_policy}` và `scripts/owner_acceptance.py`.
2. **Sửa 3 lỗi tái tạo mức trung bình** (commit `913da26`):
   - `src/wam_regtest/core_process.py`: xử lý lỗi `subprocess.SubprocessError`/decode thất bại của `lsof` trên macOS.
   - `src/wam_regtest/linux_headless.py`: lệnh `unlock`/`recover` ở chế độ headless yêu cầu ngườ vận hành gõ rõ `REAUTH`.
   - `scripts/owner_acceptance.py`: đăng ký/hủy đăng ký owned Core scope.
3. **Tiếp tục xử lý 2 findings của independent review** trên HEAD `43d94c1`:
   - **F1** — xác định nguyên nhân gốc rễ và viết patch.
   - **F2** — audit toàn bộ 115 entry bằng chứng Q02, đánh dấu 77 entry mismatch là STALE và requalify trên exact-head `f669152f`.
4. **Thêm regression contracts** trong `tests/test_q02_contracts.py` cho cả các bản fix.
5. **Đối chiếu ledger** `tests/acceptance/issue45.json`.
6. **Làm mới** `docs/Q02_CORE_AUTHENTICATION.md` và báo cáo này.
7. **Push được chủ sở hữu phê duyệt** 3 commit lên PR #129 (normal non-force push), sau đó tiến hành xử lý findings mới.

## 3. Các file thay đổi

### Bản fix 3 lỗi đầu (`913da26`)
- `src/wam_regtest/core_process.py`
- `src/wam_regtest/linux_headless.py`
- `scripts/owner_acceptance.py`
- `tests/test_q02_contracts.py`

### Đối chiếu ledger và tài liệu lần 1 (`f015fd9`)
- `tests/acceptance/issue45.json`
- `docs/Q02_CORE_AUTHENTICATION.md`

### Báo cáo tiếng Việt lần 1 (`ba0745d`)
- `docs/Q02_ENGINEERING_REPORT_VI_20261025.md`

### Xử lý findings F1 + F2 (commit mới, chưa push)
- `src/wam_regtest/custody.py` — thêm `private_temporary_directory()`
- `src/wam_regtest/core.py` — dùng `private_temporary_directory()` cho datadir disposable
- `src/wam_regtest/q02_probe.py` — dùng `private_temporary_directory()` cho Q02 owned nodes
- `tests/test_q02_contracts.py` — regression contract cho F1
- `tests/acceptance/issue45.json` — reconcile F2, đánh dấu STALE, requalify exact-head
- `docs/Q02_CORE_AUTHENTICATION.md` — cập nhật F1/F2
- `docs/Q02_ENGINEERING_REPORT_VI_20261025.md` — báo cáo này

## 4. Kết quả kiểm thử

### Source test suite (toàn bộ) sau patch F1
```
Ran 180 tests in 7.539s
OK (skipped=33)
```
- **PASS:** 147
- **SKIP:** 33 (Windows-only / Win64-only / hardware-specific)
- **FAIL:** 0

### Q02 regression contracts riêng
9/9 contract PASS, bao gồm contract mới cho `private_temporary_directory`.

### Native genuine Core smoke trên macOS ARM64
- 33/33 Q02 case PASS.
- Wallet E2E PASS.
- Security E2E PASS.
- GUI real Core E2E PASS.
- Receipt local: `/private/var/folders/3l/hqzxttpd0rx2hp38q52pkb240000gn/T/opencode/wam-q02-9985e44/local-real-core-evidence-2.json`

### Exact-head CI trước fix F1 (nguồn `f669152f`, runtime giống `43d94c1`)
Tất cả các run triggered tại `f669152f` đều green và được dùng để requalify F2:
- macOS ARM64 native real Core E2E: run **40182785805** job 121138603094
- macOS ARM64 frozen .app/.dmg E2E: run **40182785805** job 121139729216 artifact **12595735393**
- Windows x64 real Core smoke: run **40182785817**
- Windows x64 credential/vault/Q02 auth: run **40182785868** job 121137187826
- Windows x64 WSP receive + Qt read: runs **40182785794**, **40182785801**
- Linux x86_64 experimental Core REGTEST: run **40182785844**
- WSP-1 canonical 28 BIP352 vectors (macOS ARM64): run **40182785807**

### F1 — macOS frozen E2E failure (run 40184340811 tại `43d94c1`)
- Native job PASS; frozen .app/.dmg E2E FAIL.
- Lỗi: `CORE_LOCAL_NETWORK_POLICY_DENIED` → `CORE_RPC_SCOPE_FAULTED` → `Q02_NODE_START_TIMEOUT`.
- Nguyên nhân gốc: thư mục temp hệ thống trên runner macOS có ACL kế thừa (file-inherit); file `wam.conf` mới tạo bị kế thừa ACL và bị `private_bytes` từ chối. Đã tái hiện cục bộ trên macOS.
- Patch: `wam_regtest.custody.private_temporary_directory()` tạo private root dưới cwd, validate không có ACL, sau đó mới tạo temp con. Không làm suy yếu RPC auth/process ownership/network policy/fail-closed.
- Cần chạy lại CI exact-head tại commit mới sau khi push để xác nhận G3.

### F2 — acceptance evidence provenance mismatch
- Audit 115 entry có `workflow_run_id`: 77 entry khai báo sai `source_sha`/`checkout_sha` so với head SHA thực tế của workflow.
- Các run bị mismatch: `40151555636`, `40151555639`, `40151555640`, `40151555642`, `40151555712`.
- Đã đánh dấu 77 entry STALE, giữ nguyên lịch sử CI, và requalify trên exact-head `f669152f`.
- Sau reconcile: 114 entry có `workflow_run_id`, tất cả đều khớp source SHA; 0 mismatch.

### Ledger validation sau reconcile F2
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
| G3 | Frozen binary qualification (exact-source bytes) | **PENDING** — cần CI exact-head tại commit sau patch F1 |
| G4 | Negative injection / fail-closed | PASS |
| G5 | Ledger reconcile & validator PASS | **PENDING** — cần refresh bằng chứng exact-head tại commit sau patch F1 |
| G6 | Independent review / physical clean-host UX | **BLOCKED** |
| G7 | Owner merge authorization | **BLOCKED** |

## 6. Trạng thái native / frozen theo nền tảng

| Nền tảng | Loại | Trạng thái | Bằng chứng |
|---|---|---|---|
| macOS ARM64 | Native source smoke | **PASS** | Exact-head CI run 40182785805 job 121138603094 + local receipt |
| macOS ARM64 | Frozen binary (.app / .dmg) | **PENDING** | Run 40184340811 tại `43d94c1` FAIL do ACL kế thừa từ system temp; patch F1 đã sẵn sàng, cần rebuild exact-head sau push |
| Windows x64 | Native source / Q02 auth | **PASS** | Exact-head CI run 40182785868 job 121137187826 |
| Windows x64 | Frozen binary | **PASS** | Exact-head CI run 40182785868 artifact 12595296816; payload zip `c30c38eadf297047c2b7eca03faa137744c98cc184e7b2e0054e47bca4c53265` |
| Linux x86_64 | Native source / Q02 auth | **PASS** | Exact-head CI run 40182785844 job 121137286097 |
| Linux x86_64 | Desktop frozen | **PASS** | Exact-head CI run 40182785844 job 121137778108 artifact 12595122150; payload tar.gz `3ed2ff88d3893f6fd462f4e9c2a6d1022ce451973e589cc0a29fe6399eaa6b42` |
| Linux x86_64 | Headless frozen | **PASS** | Exact-head CI run 40182785844 job 121137778146 artifact 12595027351; payload tar.gz `9f8bc7e3e2e4520620cb99df28d7181e4687e37089ded5d826d1707cfe532f4a` |

## 7. Các blocker còn lại

1. **G3/G5 — Cần CI exact-head tại commit sau patch F1:** patch đã sẵn sàng cục bộ, nhưng chưa push. Sau khi chủ sở hữu phê duyệt push, cần chạy lại CI macOS frozen (và các nền tảng khác để giữ exact-head consistency), sau đó cập nhật ledger với artifact SHA-256 mới và chuyển G3/G5 sang PASS.
2. **G6 — Independent review / physical operator:** thuộc về chủ sở hữu hoặc reviewer bên ngoài; không thể tự hoàn thành bởi agent kỹ thuật.
3. **G7 — Owner merge authorization:** chủ sở hữu PR phải phê duyệt merge sau khi G6 xong.

## 8. Khuyến nghị và yêu cầu chủ sở hữu

- **Phê duyệt push** commit mới chứa patch F1 + reconcile F2 + cập nhật docs lên nhánh `acceptance/issue45-q02-core-auth-20261024` của PR #129 (normal non-force push).
- Sau khi push, chờ CI chạy xong exact-head build cho macOS frozen, Windows frozen, Linux frozen; cung cấp artifact ID/payload SHA-256 để cập nhật ledger chuyển G3/G5 từ `PENDING` sang `PASS`.
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
