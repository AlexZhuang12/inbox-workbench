# 信箱工作台（Inbox Workbench）

Windows 上的 Codex Gmail 工具，可連接多個信箱，按來源整理查詢結果，並在你確認郵件內容後寄信。使用者需自備 Google Cloud 專案的桌面 OAuth 設定。

## 安裝

- **Windows ZIP**：從 [最新 Release](https://github.com/AlexZhuang12/inbox-workbench/releases/latest) 下載 Windows ZIP 並完整解壓到自己選擇的固定位置。ZIP 已附 Windows 版 gogcli。
- **原始碼**：使用 git clone https://github.com/AlexZhuang12/inbox-workbench.git，再從 [gogcli Windows Releases](https://github.com/openclaw/gogcli/releases) 安裝 gogcli v0.48.1 或相容版本。把 gog.exe 放在 PATH，或放在專案的 bin 目錄。
- 兩種方式都需要 Python 3.10 或更新版（含 Tkinter）。可在 PowerShell 執行 python --version 確認。

**工具資料夾由你決定。** 用 ZIP 時，解壓位置就是工具存放位置。用 git clone 時，由你指定 clone 的目的地。請保留同一個資料夾供日後使用。授權 Gmail 的檔案選擇器只用來選 OAuth JSON，工具也無須另外安裝 Codex 外掛。

## 第一次設定 Google OAuth

1. 開啟 [Google Cloud Console](https://console.cloud.google.com/)，建立或選擇你有權管理的專案，再啟用 [Gmail API](https://console.cloud.google.com/apis/library/gmail.googleapis.com)。
2. 在 **Google Auth Platform → 品牌**設定應用程式名稱、支援信箱和開發人員聯絡資訊。在「目標對象」選擇適合的使用者類型。若採外部 Testing 模式，將要加入的 Gmail 地址列入測試名單。
3. 在 **資料存取權**加入並儲存這兩個權限：

   - https://www.googleapis.com/auth/gmail.readonly
   - https://www.googleapis.com/auth/gmail.send

4. 在 **用戶端 → 建立用戶端**選擇 **電腦版應用程式（Desktop app）**，下載 Google 提供的 OAuth JSON。保留在本機。
5. 雙擊 **Open Gmail Manager.cmd**，按「匯入 OAuth 設定」選取自己的 JSON。已設定過信箱工作台的 gogcli 用戶端可沿用。
6. 按「新增 Gmail」，在 Google 選取對應帳號並同意讀取與寄信。每個信箱各自同意，可共用同一個 Cloud 專案。回到工具，按「測試全部信箱」。

## 管理信箱

v0.4.0 的粉色圓角介面涵蓋主視窗、暱稱與新增信箱對話框，以及寄信預覽。從舊版升級時，使用同一 Windows 帳戶開啟新版即可沿用本機的 Gmail 授權與已儲存偏好。

在信箱列表拖曳一列，或選取後按「上移／下移」調整排序。按「編輯暱稱」可設定顯示名稱，留空即可清除。排序和暱稱會保存在本機，不影響 Gmail 地址或實際寄件人。

「查信狀態」顯示最近一次測試的結果。「寄信授權紀錄」來自本機 gogcli 設定。新增或重新授權時，下方 Google 授權區會顯示正在處理的帳號，連結備妥後可按「複製授權連結」。

## 多信箱與 Google OAuth 限制

一組桌面 OAuth 用戶端可供多個 Gmail 信箱使用。OAuth JSON 只需匯入一次，每個 Gmail 帳號仍要在 Google 頁面各自同意。新增第 3 個或更多信箱時，沿用同一組設定即可。下文的兩個帳號是驗收範例。工具每次最多並行查詢 3 個信箱，有更多信箱時會依序排入查詢。

| Google Cloud 專案狀態 | 新信箱如何授權 | Google 的限制 |
| --- | --- | --- |
| **外部 Testing（測試）** | 先把每個新 Gmail 地址加入「目標對象」的測試名單，再從工具新增。 | 測試名單最多 100 位。Gmail 測試授權在同意後 7 天到期，屆時需要重新授權。 |
| **外部 In production（正式環境），尚未驗證** | 若符合 Google 的有限對象使用例外，可從工具直接新增，由各帳號同意。 | Google 可能顯示未驗證警告。請求未核准的機密或受限制權限時，通常每個 OAuth 專案最多可累計 100 個新授權 Google 帳號。這是專案整個生命週期的額度，無法重設。 |
| **公司或學校的 Gmail** | 用帳號原有的 Google Workspace 身分授權。 | 組織管理員可能封鎖第三方工具或限制 Gmail 權限，即使專案仍有額度也可能無法授權。 |

公開 ZIP 由使用者匯入自己的 OAuth 設定，所以不同 Google Cloud 專案各自計算額度。如果日後要用同一個 OAuth 專案對外大規模發行，請確認適用的 Google 驗證要求。有限對象使用仍須遵守 Google 的資料使用政策。

[Google OAuth 發布狀態與使用者上限](https://support.google.com/cloud/answer/15549945?hl=en) · [有限對象使用例外](https://support.google.com/cloud/answer/13464323?hl=en)

## 設定本機 Codex 專案

1. 先在 Windows 雙擊 **Open Gmail Manager.cmd**，新增至少一個 Gmail，並按「測試全部信箱」確認可查詢。
2. 用同一台電腦上的 Codex 開啟你解壓或 clone 的工具資料夾。請選擇**直接含有 AGENTS.md、review.py 和 send_review.py 的那一層**，並在該資料夾對應的本機 Codex 專案開啟對話。
3. 試著輸入「查詢所有已授權信箱近七天的未讀郵件，按來源整理，並列出查詢失敗的信箱」。設定一次後，日後可從 Codex 側邊欄回到同一專案。

Gmail 授權會由本機 gogcli 保存。解壓、啟動與授權流程不會自動建立 Codex 專案或桌面捷徑。授權完成後，平常查信無須保持 Chrome 開啟。若 Codex 提示允許執行本機命令，核對提示後再繼續。

也可以在同一工具資料夾下開 PowerShell 直接測試：

```powershell
python ./review.py --query "is:unread newer_than:7d" --limit 10
```

預設每個信箱回傳最多 10 個郵件串的中繼資料，可用 `--limit` 設定為 1 至 50。結果若標記 `more_available`，代表還有其餘符合條件的結果。

## 驗收與排查

- 授權第一個帳號並查詢，再授權第二個帳號。重新查詢即可看到兩個來源，無須改提示詞或設定帳號清單。
- 如有可撤銷的測試帳號，從 Google 的第三方存取設定撤銷該帳號對測試應用程式的授權，讓本機保留舊授權紀錄。再查詢時，確認另一個信箱正常，失效帳號出現在報告中。
- **`reauthorization_required`**：在管理介面選該信箱，按「重新授權」，再於 Google 同意讀取及寄信。
- **`permission_denied`**：先確認正在使用正確帳號、Cloud 專案已啟用 Gmail API、已登記所需權限，以及 Google 同意頁已核准 Gmail 讀取權限。公司或學校帳號也要檢查組織政策。
- **`partial`** 表示部分信箱成功，**`all_failed`** 表示全部查詢失敗。查詢成功且 `threads` 是空清單時，該信箱沒有符合條件的郵件串。
- 此原型在本機執行。郵件憑證由 gogcli 管理。查詢程式只開放 Gmail 搜尋命令，Codex 會收到查詢回傳的郵件中繼資料。

第三方元件及參考來源見 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

若授權自動開在其他 Chrome 設定檔，請在管理視窗按「複製授權連結」，把原始連結貼到正確設定檔的新分頁，並保持管理視窗開啟。

## Gmail 寄送

新增信箱時，Google 在同一個流程中請求讀取與寄信權限。舊版已連接的唯讀信箱若要寄信，在管理介面選取信箱後按一次「重新授權」。

要讓 Codex 準備寄信，可以說「用 work@example.com 寄信給 recipient@example.com，請先開預覽」。Codex 會寫出本機 JSON 草稿並執行 `python .\send_review.py <草稿路徑>`。Windows 預覽列出寄件帳號、收件人、主旨和完整純文字內容。只有你按「確認寄出」後才會嘗試寄信。按取消或關閉視窗會取消。若結果是 send_unconfirmed，先在 Gmail 的寄件備份確認結果，再決定是否重送。

目前支援純文字新郵件，可以指定多個收件人。草稿格式是 UTF-8 JSON，包含 from、to（地址陣列）、subject、body。

## 授權

本專案採 [MIT 授權](LICENSE)。[第三方聲明](THIRD_PARTY_NOTICES.md)列出隨附元件及其授權。
