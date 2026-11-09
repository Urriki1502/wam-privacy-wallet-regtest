# WAM Fusion — Independent Remediation Design Review (v1.0)

**Ngày:** 06-11-2026 (Asia/Ho_Chi_Minh)  
**Mục tiêu:** làm rõ phương án kỹ thuật *trước khi* giao Codex sửa lỗi; tối thiểu hóa phạm vi thay đổi, token, CI reruns và rủi ro custody.  
**Repository:** https://github.com/Urriki1502/wam-privacy-wallet-regtest  
**Audit baseline bất biến:** PR #141, commit `b187cde17b12ae5f7c11f0611d5f4b1661bfc90b`; base `c61e3c5be4b8519dc6c4d9eb56d124fce84cf02d`; Core v0.1.13; WSP `ac55f13423620252bdbf848c7e8a280c3b84721e`.  
**Nguồn findings:** `WAM_Fusion_Phase_A_Security_Audit_Report_2026-11-06.md` (2 High, 9 Medium, 1 Low; 6 nhóm NOT VERIFIED).  
**Mức độ kiểm chứng tài liệu này:** đọc trực tiếp các module/chứng cứ GitHub tại đúng SHA; so sánh tài liệu GitHub, Apple, Qt, Microsoft, SQLite và OWASP. **Chưa chạy payload/fuzz, chưa chứng minh exploit, chưa truy cập máy Mac của chủ sở hữu.** Đây là *security design review*, không phải G7 độc lập hay cấp phép mainnet.

## Quy tắc ra quyết định

- **FACT:** đúng theo source/cấu hình được xem; **DESIGN:** giải pháp chọn để triển khai; **HYPOTHESIS:** cần tái hiện; **OPEN:** cần quyết định thiết kế/chứng cứ trước khi sửa.
- **READY TO IMPLEMENT:** giải pháp ít ảnh hưởng custody, đã xác định file và test. **DESIGN GATE:** phải chứng minh invariant/race/crash. **RESEARCH GATE:** thiếu dữ liệu hoặc hạ tầng.
- Nhóm mức độ High/Medium của audit là mức **rủi ro dự kiến khi sử dụng tiền thật**, không đồng nghĩa có khai thác thành công hoặc có CVE.
- **Không được:** tự bật mainnet, sửa WSP/core consensus, xóa/reset native anchors, xóa signed/uncertain reservations, chỉnh ledger để ép PASS, xóa lỗi lịch sử, chạy trên ví hoặc node mainnet thật, force-push, merge hoặc phát hành.
- **Local-first:** source + native macOS + frozen app/DMG trên máy local, rồi mới push và kiểm thử Windows/Linux/macOS cùng commit. Không biến 3-OS CI thành G6/G7/V19.

## Ma trận thực thi tối ưu

| ID | Kết luận | Độ sẵn sàng | Action tối ưu ngay | Chấp nhận hoàn thành khi |
|---|---|---|---|---|
| H-01 | Publisher trust chưa bao trùm Fusion | RESEARCH/OWNER | Đặc tả ký và thử bản lab, **không** tự tạo production trust | Có quy trình verify độc lập & signer/release owner |
| H-02 | `main` không protected; rulesets=0 | ADMIN READY | Owner bật bảo vệ `main` ở UI GitHub | Chống direct/force push được chứng thực bằng cấu hình |
| M-01 | Clean-device/disaster recovery thiếu proof | DESIGN GATE | ADR + threat model + test fixtures, không sửa vault | Có proof giữ irreversible state trước khi unlock spend |
| M-02 | SQLite runtime plaintext khi unlocked | RESEARCH GATE | Inventory dữ liệu, retention, forensic test | Có threat model rò dữ liệu & biện pháp đã test |
| M-03 | Xóa secret trong RAM best effort | RESEARCH GATE | Lifetime/copies audit; không tuyên bố zeroization | Có mitigation theo giới hạn runtime đã chứng minh |
| M-04 | KDF cố định & password yếu khả thi | DESIGN GATE | Benchmark + password policy; format upgrade riêng | Versioned migration + fixture cross-platform PASS |
| M-05 | Generation cap 4096 / Linux 10000 | DESIGN GATE | Stress near-limit chỉ với fixtures | Rotation/compaction crash-safe, reservation preserved |
| M-06 | Thiếu auto-lock theo idle/OS session | DESIGN GATE | State-machine + race tests trước code | Không approval stale; lock đúng khi worker in-flight |
| M-07 | Actions tham chiếu tag mutable | READY TO IMPLEMENT | Pin full verified SHAs trong 11 workflow | Diff chỉ uses/permissions; CI unaffected |
| M-08 | RPC slow-trickle/hang nghi vấn | REPRODUCE FIRST | Bounded lab transport fixture | Trước/sau có evidence; không retry write |
| M-09 | Manual peer không được crypto-authenticate | RESEARCH/NETWORK | Threat model, V19/partition lab, không giả tăng bảo mật | Có P2P test/định nghĩa trust rõ |
| L-01 | Backup verifier nhận <3 vị trí từ GUI | READY AFTER MINI DESIGN | Backend-owned one-use challenge | One/two/replay/substitution FAIL; exact 3 PASS |

## H-01 — Toàn vẹn **nhà phát hành** gói Fusion

**FACT:** `scripts/build_macos_bundle.sh` sử dụng `codesign --force --sign - --timestamp=none "$APP"` và ghi app/DMG là ad-hoc, chưa notarized. Core v0.1.13 được pin member hash riêng; điều đó **không** chứng minh Fusion wrapper được nhà phát hành cho phép. `docs/SBOM_PREP_HOST.md` chỉ liệt kê dependency host, không phải frozen SBOM. [Source](https://github.com/Urriki1502/wam-privacy-wallet-regtest/blob/b187cde17b12ae5f7c11f0611d5f4b1661bfc90b/scripts/build_macos_bundle.sh#L90-L104).

**DESIGN chọn:** chia **build không có release secrets** và **ký/phát hành có kiểm soát bởi release owner**. Tạo manifest nguồn + WSP/Core member pin + hash của *artifact thành phẩm sau ký*; ký metadata bằng khóa do owner quản lý, người tải xác minh bằng public trust root phân phối độc lập. macOS: Developer ID + hardened runtime + notarization/stapling *nếu có chứng thư phù hợp*. Windows: Authenticode + kiểm tra signer chain và timestamp. Linux: detached signature của package/manifest, khóa ký xác minh bên ngoài package. Signature workflow không được sửa byte Core đã được chứng minh từ upstream; đặc biệt thử mâu thuẫn giữa signing outer app và hash nested `wamd`/`wam-cli` trước khi chốt packaging.

**Không chọn:** chỉ ghi `SHA256SUMS.txt` cùng ZIP; tự tạo khóa trên CI runner rồi gọi là publisher; tự thay Core gốc bằng build mới để dễ ký; chỉ dựa vào chữ ký Core để suy ra chữ ký Fusion.

**Việc Codex có thể làm ngay:** viết `docs/security-audit/H01_RELEASE_TRUST_ADR.md`, kiểm tra thao tác ký thử **trên bản copy disposable**, không có khóa sản xuất, đo Core member hashes trước/sau. **Không được tự bật notarization/release**. **DoD:** quy trình phân phối trust key, key custody/rotation/revocation, chứng thực offline, phân tách CI build vs owner release, output SHA256/SBOM/signer report. **Chặn mainnet release** cho đến khi hoàn tất.  
**Tham khảo:** https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution

## H-02 — Ruleset GitHub `main`

**FACT:** GitHub API trả `main.protected=false`, `/rulesets=[]` ngày 06-11-2026. Đây là **rủi ro quản trị/supply chain**, không phải bug ký ví và không phải điều kiện buộc dừng REGTEST local audit.

**DESIGN chọn (owner thực hiện):** Ruleset chỉ áp dụng `main`; require pull request; block force push; block branch deletion; không cấp bypass cho AI/tool token. Thêm required checks sau khi đối chiếu tên check thực sự chạy trên target `main` (CI có workflow manual/PR/path khác nhau); chọn GitHub Actions làm expected app nếu khả thi. Với repo chủ yếu một người, không bật mandatory human approval **cho đến khi có reviewer có thể approve**, để tránh tự khóa merge. Xác minh bằng UI/effective rules, không thử push phá chính sách.

**Không chọn:** bật 20 required checks ngay; bảo vệ mọi feature branch khiến Codex không thể push; giao Codex token Full Access tự chỉnh rules rồi tự miễn trừ. **DoD:** ảnh hoặc biên bản cấu hình + mô tả bypass actors + rule enforcement. Không cần sửa source; không làm gián đoạn PR #141.

**Tham khảo:** https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets

## M-01 — Khôi phục máy sạch, mất anchor, mất journal (độ khó CAO NHẤT)

**FACT:** `bip39_recovery_proof.py` chủ ý trả `same_chain_only=true`, `clean_device_recovery=false`, `signed_reservations_restored=false`, `signer_allowed=false`, `broadcast_allowed=false`. `wallet_recovery.py` bảo tồn native anchor floor và từ chối divergent future; `Core migratewallet` không chuyển Core identity của Fusion. [Recovery proof](https://github.com/Urriki1502/wam-privacy-wallet-regtest/blob/b187cde17b12ae5f7c11f0611d5f4b1661bfc90b/src/wam_regtest/bip39_recovery_proof.py#L80-L97).

**Tách 3 loại quyền:** (R1) **key identity** từ 12 từ; (R2) **chain-visible wallet state** từ scan đúng chain, đúng genesis, đầy đủ history/UTXO; (R3) **off-chain irreversible state** gồm giao dịch đã ký/uncertain, reservation, Core/native owner provenance. R1+R2 **không chứng minh** R3; một signed tx chưa broadcast có thể không hiện trên blockchain.

**DESIGN nghiên cứu (KHÔNG triển khai signer):**
1. Chế độ `RECOVERED_READ_ONLY`: tạo **profile mới sạch** từ mnemonic test, attestation genesis/Core, rescan toàn bộ đúng chain; chỉ xem địa chỉ/balance/history; tuyệt đối không ghi lên anchor/profile cũ.
2. Chế độ `STATE_CONTINUITY_VERIFIED`: yêu cầu backup journal được xác thực, cùng wallet identity, bản ghi signed/uncertain đầy đủ, native-authorized migration proof; create-only checkpoint và CAS vào anchor mới, crash-safe; nếu bất cứ thứ gì không khớp -> READ_ONLY/BLOCKED.
3. Tình huống mất **toàn bộ** journal nhưng còn keys: chưa có phương án nào đảm bảo tự động khôi phục quyền ký trong mọi tình huống. Cần policy được owner và reviewer phê duyệt về các UTXO rủi ro, thời gian/quy trình reconciliation, cảnh báo về signed tx vô hình. Không cho Codex tự chọn timeout và tự giải phóng.

**Test vectors bắt buộc:** mất 1 anchor; mất cả anchor+ciphertext; dùng backup cũ; backup mới; signed-before-crash; broadcast-uncertain; chain partition; same-chain restore; wrong genesis; wrong OS; wrong Core hash; concurrent owner; crash tại mỗi bước ghi mới; duplicate tx; reorg. **Không reset native anchors hay data retained owner.**

**Deliverable trước code:** `M01_RECOVERY_THREAT_MODEL.md`, `M01_RECOVERY_ADR.md`, state/invariant table, migration format proposal, fixture-only 2-machine scenarios, proof of refusal. **DESIGN GATE:** phải được review riêng trước khi viết any wallet writer. **Không được báo M01 Fixed bằng BIP39 rescan đơn thuần.**

## M-02 — SQLite runtime plaintext / dữ liệu privacy

**FACT:** WSP pinned `store.py` lưu coins/tweaks/contacts/labels/history/reservations SQLite chưa mã hóa, `PRAGMA journal_mode=DELETE`, `synchronous=FULL`; mật khẩu/seed không nằm rõ trong schema được rà soát. `bip39_spend_session.lock()` cố ý **giữ** runtime khi signed/uncertain/faulted để phục vụ forensic, nên unlink luôn không phải giải pháp đúng.

**DESIGN chọn theo hai giai đoạn:**
- **Lab đo trước:** tạo synthetic history/contacts/labels; lập inventory `db`, `-journal`, swap/crash dump/OS backup/snapshot (trong giới hạn quan sát được), trên macOS APFS/Windows/Linux. Đo vòng đời file khi lock sạch, lock uncertain, crash, restart. Cấm quét seed thật.
- **Mitigation tối thiểu:** giới hạn thời gian mở, bảo vệ quyền owner, disable backup không phù hợp, giảm PII/retention, redaction logs, không đưa runtime vào artifact/evidence. Nếu mục tiêu privacy cần encryption-at-rest cả khi unlocked, viết ADR tách riêng cho SQLCipher/encrypted VFS hoặc mô hình in-memory + encrypted snapshots **với consistency proof**; không đổi sqlite engine ở B1.

**Reject:** tự `unlink` runtime uncertain, `PRAGMA secure_delete` như cam kết SSD secure erase, bật WAL/SQLCipher mà chưa kiểm tra compatibility WSP/schema/rollback, đổi toàn bộ state storage chỉ để qua audit. **DoD:** report bề mặt lộ dữ liệu có thể kiểm chứng, mitigations + regression cleanup/fault retention; encryption rollout nếu có cần format migration và crash tests.

## M-03 — Secret lifetime / RAM

**FACT:** `bip39_12.py` tạo immutable `seed: bytes` rồi copy sang `bytearray`; close chỉ ghi đè bytearray. GUI mnemonic/`str`/Python scalar và `_password` có copies ngoài kiểm soát. Mục tiêu “xóa tuyệt đối RAM trong Python” là không chứng minh được.

**DESIGN chọn:** audit các đoạn seed/passphrase đi qua `bip39_12.py`, `bip39_seed_vault.py`, `bip39_owner_backend.py`, `wallet_session.py`, WSP; giảm `bytes(...).decode()` không cần thiết và lifetime plaintext, xóa UI seed ngay sau xác nhận, không lưu log, không xuất core dumps trong bản release nếu có cơ chế chính thức, giảm thông tin trong error. Tách nghiên cứu signer process/native buffer (lockable RAM/avoid dump) thành milestone mới vì thêm IPC/process lại tạo trust boundary mới. Bản hiện tại không được tuyên bố chống same-UID malware/root.

**Reject:** tự viết hàm overwrite `str` CPython, patch crypto primitives, tuyên bố `mlock` che mọi native copies, gỡ recovery functionality để giảm RAM. **DoD:** explicit secret-flow diagram + test no secret in diagnostics/artifacts/UI post-lock + review mitigation limits. Không yêu cầu phá kho dữ liệu RAM thật.

## M-04 — Password/KDF chống đoán offline

**FACT:** WSP `keystore.py` dùng AES-GCM và scrypt `N=2^15, r=8, p=1` + random salt, AAD purpose/network, envelope `WAMSP02`; minimum 12 bytes là kiểm tra **độ dài**, không đo entropy. OWASP 2026 đề xuất các cấu hình scrypt mạnh hơn (ví dụ `2^17,r=8,p=1` hoặc tổ hợp chi phí tương đương); đề xuất guideline **không** tự chứng minh bản cũ bị crack.

**DESIGN:** bắt đầu bằng (1) thử password quality policy thân thiện passphrase, danh sách password yếu/chuỗi lặp, NFKD/Unicode; (2) benchmark KDF trên Mac/Windows/Linux thấp nhất được hỗ trợ cho tạo/mở/khôi phục; (3) chọn parameter theo entropy + UX latency mục tiêu; (4) nếu tăng KDF hoặc đổi Argon2id, **tạo envelope version/purpose mới có migration giao dịch được xác thực** ở nguồn WSP được review, với dual-read có điều kiện và single-write mới. Không tự sửa checkout WSP pinned hoặc đổi MAGIC tại runtime.

**Tests:** old envelope read; wrong password; modified salt/nonce; downgrade; Unicode; tiny password; costly input exhaustion; crash midway migration; checksum/Core independent. **Reject:** nâng `N` bằng tìm/thay; reencrypt silently all old profiles; cho phép weak password để tương thích mainnet không giới hạn. **DoD:** measured benchmark, ADR versioned envelopes, accepted memory/cpu bounds, fallback denied safely.  
**Tham khảo:** https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html

## M-05 — Checkpoint/journal generation limits

**FACT:** Q06 scanner checkpoint `MAX_CHECKPOINT_GENERATIONS=4096`; Linux root-witness read giới hạn 10.000 `.anchor` và kiểm tra các generations liên tiếp. Đây là giới hạn availability dài hạn có căn cứ; không phải bằng chứng mất khóa trực tiếp.

**DESIGN:** Phase 1: readonly metrics/cảnh báo sớm (ví dụ 80/90% cap) và fixture stress sát ngưỡng; định lượng kích thước, độ trễ, write rate/ngày. Phase 2 ADR cho **epoch/compaction dưới CAS**: có authenticated summary mới chứng minh đầy đủ state, giữ reservation signed/uncertain, transition được journal trước khi xóa bất cứ gì, native witness/chứng thực chủ sở hữu; crash-cut trước/sau mỗi fsync/anchor advance đều trả về trạng thái xác minh được hoặc từ chối. Cần review logic crash trước implementation.

**Reject:** tăng số 4096/10000 tùy tiện; reset counter về 1; xóa file `.anchor`/snapshot; bỏ no-gap check. **DoD:** fixture đến/quá cap + steady-state long-run + failure injection cross-platform; no irreversible state loss. Nếu chưa đạt, giữ fail-closed và báo giới hạn.

## M-06 — Auto-lock/OS session lock: chốt kiến trúc trước khi viết GUI

**FACT:** GUI Q06 chỉ có manual Lock; executor một thao tác in-flight; `wallet_executor.request()` timeout **không hủy operation**; `PaymentApproval.open()` async và dialog có thể chờ; không có timeout/OS lock ở đường này. `wallet_session.lock()` và `bip39_spend_session.lock()` có logic bảo toàn uncertain; gọi `lock` từ timer khi worker busy có thể bị từ chối.

**DESIGN đề xuất: máy trạng thái có _authorization epoch_ và hai lớp khóa.**
- `UNLOCKED(epoch=N)` -> nhận idle/OS lock -> **đồng bộ** `LOCK_REQUESTED(epoch=N+1)` tại GUI/security gate; ngay lập tức vô hiệu các modal approvals, xóa/che dữ liệu UI, không cấp consent mới. Không dùng việc xóa UI như bằng chứng backend đã khóa.
- Backend sign/broadcast nhận *current epoch + commitment*; validate dưới serialized owner boundary ngay trước **điểm không thể đảo ngược**. Nếu lock request đến trước authorization linearization -> refuse. Nếu user đã approve và native Sign/Broadcast **thật sự bắt đầu** trước đó, không kill/cancel/retry; thao tác hoàn tất hoặc giữ uncertain, rồi khóa session dưới owner executor.
- Khi idle/OS event xảy ra lúc worker busy, request lock được ghi theo state/flag độc lập được đồng bộ (không chỉ `executor.submit('lock')` có thể bị từ chối); một lệnh close được hàng đợi một cách có kiểm soát sau worker, và UI tiếp tục deny cho đến khi state `LOCKED`/`FAULTED`. **Không cho phép Sign/Broadcast sử dụng một approval còn sống từ epoch trước**.
- Unlock bắt buộc password + original Core/native anchor attestation; không dùng OS unlock tự unlock ví; không giải phóng signed/uncertain reservation. Khởi động lại app ở trạng thái locked.
- **Giá trị thiết kế đề xuất, chưa chốt UX:** default idle 5 phút, các lựa chọn 1/5/15 phút; OS session lock/suspend -> lock ngay. Sự kiện hoạt động là thao tác người dùng thực trong app, không phải timer/sync/network activity tự gia hạn. Nếu không nhận được native OS event đáng tin trên một OS, đánh dấu giới hạn thay vì giả PASS.

**Nguồn event:** Qt `QApplication.installEventFilter()` cho keyboard/mouse; macOS `NSWorkspace` active-session/sleep notifications; Windows `WM_WTSSESSION_CHANGE` + đăng ký notification; Linux systemd-logind session `LockedHint`/desktop-specific signal cần xác thực cơ chế trên từng desktop. Qt event filter một mình **không** tương đương OS screen lock.

**Tests trước PR:** countdown/idle, keyboard/mouse, modal đang mở, approve-during-show race, timer đúng lúc Prepare complete, sign-in-flight, broadcast-uncertain, worker timeout, OS lock/wake, GUI hidden, lost lock event, GUI unresponsive, Core disconnect, 2 windows, quit/restart, cross-platform native/frozen. **Không chốt CI PASS bằng synthetic OS event nếu chưa có native observation riêng.**

**Output B1B bắt buộc:** `M06_AUTOLOCK_ADR.md` + state-transition table + lock event adapters + negative tests skeleton; **review rồi mới cho Codex code**. **Reject:** timer chỉ gọi `_command('lock')`; kill executor; cancel signed tx; auto-unlock theo OS.  
**Tham khảo:** https://doc.qt.io/qt-6/eventsandfilters.html ; https://developer.apple.com/documentation/appkit/nsworkspace/sessiondidresignactivenotification ; https://learn.microsoft.com/en-us/windows/win32/termserv/wm-wtssession-change

## M-07 — Pin CI Actions, nhỏ và rõ

**FACT được kiểm tra ở 11 workflow `.github/workflows/`:** các `uses:` bên ngoài được thấy thuộc **4 Actions**: `actions/checkout@v4`, `actions/setup-python@v5`, `actions/upload-artifact@v4`, `actions/download-artifact@v4`. Đa số job đã khai báo `permissions: contents: read`; một số cần `actions: read`.

**DESIGN READY:** lấy immutable full commit SHA **từ chính repository phát hành Action**, kiểm tra release/tag tương ứng và hash/owner; thay `uses` tương ứng trong cả 11 YAML, giữ comment phiên bản; kiểm tra toàn bộ `uses:` không sót; quyền token theo job tối thiểu; PR từ fork không được cấp release secrets; validate YAML và chạy workflow hiện hữu. GitHub Actions dependency lockfile hiện là phương án mạnh hơn nếu project hỗ trợ; không cần đưa thêm tooling vào B1 nếu chỉ để nâng security đơn giản.

**Không chọn:** sao chép SHA từ blog/ngẫu nhiên; chuyển sang latest tag không pin; thay token quyền write rộng để khắc phục workflow failure; viết lại toàn bộ CI làm mất evidence. **DoD:** no mutable `uses:` left, provenance of every selected SHA, workflow parse PASS, tests unaffected, artifact compare.  
**Tham khảo:** https://docs.github.com/en/actions/reference/security/secure-use

## M-08 — Transport liveness: chưa được phép sửa khi chưa tái hiện

**FACT:** `json_rpc.py` có HTTP response size cap; `response.read(cap+1)` và socket timeout, nhưng không có **wall-clock absolute deadline** cho cả stream; `wallet_executor.py` giữ pending khi caller timeout, đúng chính sách không retry financial writes. **HYPOTHESIS:** peer/Core bị chậm dần từng chunk có thể trì hoãn executor/lock.

**Thiết kế thử:** tạo fixture loopback chỉ trả chunks đều đặn trước mỗi socket timeout nhưng tổng thời gian vượt ngân sách; đo wall-clock, resource, state, GUI refusal và original-core binding. Lab riêng dùng transport giả **chỉ để tái hiện**; nghiệm thu vẫn yêu cầu genuine Core. Nếu tái hiện, đưa absolute monotonic deadline và bounded read worker *chỉ ở transport read*, không ngắt/retry write path; vẫn preserve original operation pending nếu có uncertainty. Phân loại Core thật có thể gây lỗi này không là câu hỏi khác.

**Reject:** tăng timeout 240/600/900 để che; tự cancel/kill worker khi timeout; tự gửi lại RPC write. **DoD:** deterministic before/after slow-trickle regression; native Core unaffected; UI lock eventually safe and states accurately reported.

## M-09 — Peer trust/P2P/mainnet

**FACT:** `shared_regtest.py` chỉ kiểm tra địa chỉ IP/port, handshake version/subversion và giới hạn peers; không có channel binding cryptographic identity cho remote peer. Đây là cơ chế REGTEST manual được xác định trước, **không** phải bằng chứng peer có thể điều khiển Core RPC hoặc ký ví. BIP352 không ẩn danh IP.

**DESIGN REGTEST:** giữ manual P2P cho V19; actual two-host setup test: peer sai genesis, peer giả, partition, stale chain, fork/reorg, unexpected peers, self-peer, inbound/outbound, RPC vẫn loopback; kiểm tra bảo toàn signed/uncertain. Peer host trust được người vận hành chọn; chỉ version string không là identity proof.

**DESIGN MAINNET (tương lai, ngoài PR):** dùng Core v0.1.13 native peer discovery/chain validation, nghiên cứu eclipse resistance, peer diversity, transport privacy/Tor nếu hỗ trợ/được review. Không phát minh lớp xác thực peer trong Fusion UI rồi tuyên bố bảo vệ underlying Core TCP nếu chưa có crypto-binding thực sự. **DoD:** V19 actual physical evidence + network threat model và rõ giới hạn privacy; không tự bật auto-discovery trong REGTEST hiện tại.

## L-01 — Backup 3-word challenge: cụ thể hóa cơ chế đủ để code

**FACT:** `bip39_backup_page.py` (GUI) gọi `random.sample(range(1,13),3)` và chuyển **positions và answers** vào `backup_verify`. `bip39_owner_backend.py:665-700` cho phép positions không rỗng (1–12 distinct), nên một từ chính xác cũng có thể viết acknowledged HMAC. Backend đã có MAC cho acknowledgement; hạn chế nằm ở **quyền tạo/kiểm soát challenge**, không ở BIP39 checksum.

**DESIGN đã chọn:** chuyển quyền tạo challenge sang `Bip39ReadOnlyBackend`, sinh đúng **3 vị trí khác nhau** bằng CSPRNG `secrets.SystemRandom().sample(...)`, giữ trong *memory owner session* với `challenge_id` opaque, profile/seed identifier, session epoch, expiry (đề xuất 120 giây), used/invalidated bit. GUI chỉ yêu cầu challenge và hiển thị 3 positions; submission **không gửi positions tự chọn**, chỉ `challenge_id + 3 answers`. Backend xác minh current challenge, exact 3, chưa dùng/chưa hết hạn/đúng profile/epoch, so sánh expected phrases, và **consume** challenge một lần trước khi ghi ack. Cancel, lock, restart, seed change, wrong answer hoặc timeout invalidates; UI có thể yêu cầu challenge mới, không tự tiết lộ từ đúng. Không persist challenge hoặc mnemonic. Giữ HMAC/sidecar envelope hiện hữu, trừ khi test phát hiện vấn đề độc lập.

**Test:** exact 3 correct PASS; 1/2 vị trí FAIL; altered positions FAIL; answer replay FAIL; old id FAIL; wrong wallet FAIL; expired FAIL; lock/reopen FAIL; wrong word FAIL; same-challenge simultaneous requests => only one success; deferred backup obtains fresh challenge; no seed/password in error/log; genuine frozen Qt flow vẫn PASS. **Lưu ý** GUI trước giờ hiển thị word grid, nên nếu vẫn còn mnemonic trong UI khi challenge chạy, không gọi nó là proof người dùng đã viết ra giấy; đây là UX acknowledgement, không chứng minh backup offline tồn tại.

**Files:** `src/wam_regtest/bip39_backup_page.py`, `bip39_fusion_gui.py`, `bip39_owner_backend.py`, command allowlist trong `wallet_executor.py` nếu thêm RPC nội bộ, `tests/test_q06_bip39_backup_ack.py`, `tests/test_q06_bip39_owner_backend.py`, `tests/test_q06_bip39_fusion_gui.py`. **DoD:** backend alone denies bypass (independent of GUI), original HMAC still valid, old profile reading unchanged, no altered Core/WSP pins. **READY TO IMPLEMENT** sau khi cố định contract của `challenge_id`/expiry.

## Sáu NOT VERIFIED — đây là chứng cứ cần thu thập, KHÔNG phải sáu lỗ hổng đã kết luận

| NV | Nghiên cứu/thử nghiệm cụ thể | Output bắt buộc | Trạng thái triển khai |
|---|---|---|---|
| NV-01 Crypto/BIP352/nonce | BIP39 128→512-bit vectors, WSP BIP352/PSBTv2 differential tests với thư viện độc lập, malformed points/PSBT parser fuzz, native secp256k1 hash + nonce code audit | vector diff + seed corpus redacted + crash-free parser stats | Research; không thay crypto trong B1 |
| NV-02 Dependencies/loader | SBOM CycloneDX/SPDX từ *final frozen artifacts* trên 3 OS; kiểm tra wheel native, Qt plugins, OpenSSL, SQLite, DLL/dylib/ELF loader/RPATH và CVE thời điểm audit + reachability | per-artifact SBOM + dated SCA + exception ledger | Research; có thể chạy song song |
| NV-03 Power-cut/dual rollback | Disposable wallet + fault injection theo fsync/CAS/anchor/SQLite, separate physical power-cut lab, rollback both stores and evidence retention | crash-state transition map + recovery/refusal proof | High-risk lab; không trên máy chủ sở hữu |
| NV-04 GUI/clipboard | Recipient dài/Unicode, clipboard substitution, DPI 100/125/150, accessibility/screen reader, stale modal, amount/fee normalization across OS | physical screenshot/test receipts không chứa seed | Research then UX fixes |
| NV-05 Network/privacy | Hai host V19, peer compromise, packet capture có phép, log/crash/artifact secret scan, privacy disclosure | redacted PCAP metadata + 2-host proof | G6/V19 + network review riêng |
| NV-06 Chain/fee/migration | Reorg 1/12/100, fee/dust exact-intent policy, full-history same-chain restore, *separate* v0.1.11→v0.1.13 identity migration test | funds-correctness matrix + owner-approved migration ADR | Research; cấm silent migration |

## Điều kiện giữ nguyên (không được đổi để sửa lỗi)

1. `REGTEST` only, `mainnet_allowed=false`, localhost-only Core RPC, manual P2P unchanged; no live mainnet seeds/funds.
2. Core signed v0.1.13 original member hashes and WSP source pin remain unchanged; wallet profile old Core/version + native anchors không tự migrate.
3. `prepare` validates recipient/amount/fee, durable reservation; `sign` validates exact commitment and UTXO/tip; `broadcast` requires distinct approval and persists uncertain BEFORE network call.
4. Timeout/exception from sign/broadcast không tự retry, không tự release signed/uncertain, không adopt Core/owner bằng PID.
5. Existing historical FAIL receipts and `tests/acceptance/issue45.json` kept as-is pending evidence-specific owner decision; G6/G7/V19 blocked, Q06 `accepted=false`.
6. Qt dialog `PaymentApproval.open()` liveness fix preserved; no return to blocking `exec()` for this flow.

## Thứ tự triển khai tối ưu token

**T0 — Owner (không dùng Codex credits):** cấu hình Ruleset `main` cho H-02 nếu muốn bảo vệ sớm; review thay đổi UI, không tự cấp bypass cho agent.

**T1 — Codex small isolated PR A (L-01):** làm backend challenge contract + tests; chỉ 5–7 file chính; local focused tests ⇒ toàn bộ unit ⇒ macOS native/frozen ⇒ push ⇒ 3-OS CI. **Không đồng thời auto-lock.**

**T2 — Codex small isolated PR B (M-07):** sửa 11 workflow / bốn Actions, kiểm chứng SHAs và YAML + 3-OS CI; có thể song song chuẩn bị design M06 bằng reviewer chỉ-đọc, nhưng không concurrent writer cùng worktree.

**T3 — DESIGN ONLY M06:** ADR state machine/epoch/OS adapters; security review và test matrix rồi mới implementation PR. T1/T2 không cần chờ M06.

**T4 — RESEARCH ONLY M01/M05:** custodial recovery và snapshot compaction; không cho Codex sửa runtime cho đến khi design gate PASS. M02/M03/M04 thí nghiệm trên disposable lab, sau đó mới roadmap implementation.

**T5 — Independent audit NV-01/02/03/04/05/06 + M08 reproduction:** phân công người/runner; tách tìm lỗi và sửa lỗi; giữ bằng chứng exact SHA.

**T6 — H01 release architecture/owner credentials:** chỉ sau khi source/hardening ổn định; ký final artifacts phải có owner-controlled trust root. Không cần ký production gấp để tiếp tục REGTEST.

**T7 — Full requalification + G6/G7/V19:** native/frozen exact commit, human Mac/Windows/Linux, 2 actual Core hosts, independent security reviewer, Q06 ledger reconcile đúng từng case. Mainnet promotion là một dự án/quyết định khác.

## Quy tắc giảm token cho Codex

- Giao **một finding/một PR** khi ảnh hưởng runtime; chỉ những module được chỉ định, không đọc lại 500 file repo sau khi handoff đã có source + invariant + test targets.
- Prompt mỗi nhiệm vụ có đủ: `exact SHA`, `finding ID`, `allowed files`, `must-preserve invariants`, `focused tests`, `LOCAL-FIRST`, `stop conditions`, `output report`.
- Trước khi viết: kiểm tra `git status`, clean worktree, engineering lease, đúng branch, đọc *tối đa* các file trong phạm vi; Codex được mở rộng chỉ khi ghi lý do phụ thuộc cụ thể.
- Sửa theo test chứng minh lỗi, không tái cấu trúc vô cớ, không tăng timeout tùy tiện, không dùng CI để debug lỗi có thể tái hiện Mac local.
- Không push giữa các lỗi local; push sau local gate; CI Windows/Linux không thể được thay bằng macOS unit tests.
- Mỗi kết quả tạo mapping `finding→code diff→test→source SHA→artifact hash→residual risk` trong `ENGINEERING_HANDOFF.md`, không claim done nếu lacks proof.
- Không dùng thuật ngữ **independent G7 review** cho Codex tự review code của mình; cần người khác có năng lực và chứng cứ riêng.

## Prompt ngắn mẫu **CHỈ KHI** chốt từng thiết kế

```text
Continue in ~/Documents/WAM-Q06-Audit-20261102.
Read AGENTS.md, ENGINEERING_HANDOFF.md, and
 docs/security-audit/WAM_Fusion_Security_Remediation_Design_Review_2026-11-06.md.
Verify exact source/branch and acquire engineering lease.
Implement ONLY finding <ID> per its DESIGN/DoD section.
Do not widen scope or weaken the nonnegotiable invariants.
Prove failing negative regression before fixing (where applicable).
Run focused → unit → local native/frozen Mac tests; fix locally.
Only after local gate PASS may you push scoped branch and run native CI.
Preserve PR #141 and historical evidence; no merge/mainnet/release.
Report finding→diff→test→exact commit→remaining risk.
```

## Tài liệu tham chiếu đã đối chiếu

- Baseline PR #141: https://github.com/Urriki1502/wam-privacy-wallet-regtest/pull/141
- WAM Fusion audit: `docs/security-audit/WAM_Fusion_Phase_A_Security_Audit_Report_2026-11-06.md`
- WSP pinned keystore/store: https://github.com/Urriki1502/wam-silent-payments/tree/ac55f13423620252bdbf848c7e8a280c3b84721e/src/wam_sp
- GitHub Rulesets: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets
- GitHub Actions secure use: https://docs.github.com/en/actions/reference/security/secure-use
- Apple notarization: https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution
- Qt event filters: https://doc.qt.io/qt-6/eventsandfilters.html
- Apple session notification: https://developer.apple.com/documentation/appkit/nsworkspace/sessiondidresignactivenotification
- Microsoft WTS lock: https://learn.microsoft.com/en-us/windows/win32/termserv/wm-wtssession-change
- OWASP KDF: https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html
- SQLite WAL/consistency context: https://www.sqlite.org/wal.html

**Phạm vi đánh giá:** quyết định thiết kế khả thi, không phải kết quả fix hoặc security certification. Với các mục đánh dấu DESIGN/RESEARCH GATE, nhiệm vụ Codex đầu tiên là tạo bằng chứng/ADR chứ không triển khai writer. Tuyệt đối không hứa 'an toàn tuyệt đối'.
