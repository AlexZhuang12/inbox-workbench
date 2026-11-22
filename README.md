# 信箱工作台（Inbox Workbench）

Windows 上的 Codex Gmail 工具。每次執行從 gogcli 取得最新授權清單，最多同時查詢 3 個信箱。可繼續新增帳號。每個信箱單獨回傳來源、查詢結果及錯誤。預設每個信箱最多回傳 10 個郵件串的中繼資料，可調到 50 個。

## 安裝

- **Windows ZIP**：從 [v0.3.1 Release](https://github.com/AlexZhuang12/inbox-workbench/releases/tag/v0.3.1) 下載 inbox-workbench-v0.3.1-windows.zip 並完整解壓。ZIP 已附 Windows 版 gogcli。
- **原始碼**：使用 git clone https://github.com/AlexZhuang12/inbox-workbench.git，再從 [gogcli Windows Releases](https://github.com/openclaw/gogcli/releases) 安裝 gogcli v0.48.1 或相容版本。把 gog.exe 放在 PATH，或放在專案的 bin 目錄。
- 兩種方式都需要 Python 3.10 或更新版（含 Tkinter）。可在 PowerShell 執行 python --version 確認。

## 第一次設定 Google OAuth

1. 開啟 [Google Cloud Console](https://console.cloud.google.com/)，建立或選擇你有權管理的專案，再啟用 [Gmail API](https://console.cloud.google.com/apis/library/gmail.googleapis.com)。
2. 在 **Google Auth Platform → 品牌**設定應用程式名稱、支援信箱和開發人員聯絡資訊。在「目標對象」選擇適合的使用者類型。若採外部 Testing 模式，將要加入的 Gmail 地址列入測試名單。
3. 在 **資料存取權**加入並儲存這兩個權限：

   - https://www.googleapis.com/auth/gmail.readonly
   - https://www.googleapis.com/auth/gmail.send

4. 在 **用戶端 → 建立用戶端**選擇 **電腦版應用程式（Desktop app）**，下載 Google 提供的 OAuth JSON。保留在本機。
5. 雙擊 **Open Gmail Manager.cmd**，按「匯入 OAuth 設定」選取自己的 JSON。已設定過信箱工作台的 gogcli 用戶端可沿用。
6. 按「新增 Gmail」，在 Google 選取對應帳號並同意讀取與寄信。每個信箱各自同意，可共用同一個 Cloud 專案。回到工具，按「測試全部信箱」。

## 用 Codex 查信

在 Codex 開啟解壓後的資料夾，輸入「查詢所有已授權信箱近七天的未讀郵件，按來源整理，並列出查詢失敗的信箱」。你也可在同一資料夾開 PowerShell：

```powershell
python ./review.py --query "is:unread newer_than:7d" --limit 10
```

## 驗收與排查

- 授權第一個帳號並查詢，再授權第二個帳號。重新查詢即可看到兩個來源，無須改提示詞或設定帳號清單。
- 如有可撤銷的測試帳號，從 Google 的第三方存取設定撤銷該帳號對測試應用程式的授權，讓本機保留舊授權紀錄。再查詢時，確認另一個信箱正常，失效帳號出現在報告中。
- reauthorization_required 表示該信箱需要重新授權。在管理介面選取該信箱並按「重新授權」，再於 Google 勾選讀取及寄信。Google 外部 Testing 模式的 Gmail 授權通常約七天需要重授。
- partial 代表部分信箱成功，仍可使用其結果。all_failed 代表全部查詢失敗。查詢成功但 threads 為空代表該信箱沒有符合條件的郵件串。
- 此原型在本機執行。郵件憑證由 gogcli 管理。查詢程式只開放 Gmail 搜尋命令，Codex 會收到查詢回傳的郵件中繼資料。

第三方元件及參考來源見 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

若授權自動開在其他 Chrome 設定檔，請在管理視窗按「複製授權連結」，把原始連結貼到正確設定檔的新分頁，並保持管理視窗開啟。

## Gmail 寄送

新增信箱時，Google 在同一個流程中請求讀取與寄信權限。舊版已連接的唯讀信箱若要寄信，在管理介面選取信箱後按一次「重新授權」。

要讓 Codex 準備寄信，可以說「用 work@example.com 寄信給 recipient@example.com，請先開預覽」。Codex 會寫出本機 JSON 草稿並執行 `python .\send_review.py <草稿路徑>`。Windows 預覽列出寄件帳號、收件人、主旨和完整純文字內容。只有你按「確認寄出」後才會嘗試寄信。按取消或關閉視窗會取消。若結果是 send_unconfirmed，先在 Gmail 的寄件備份確認結果，再決定是否重送。

目前支援純文字新郵件，可以指定多個收件人。草稿格式是 UTF-8 JSON，包含 from、to（地址陣列）、subject、body。

## 授權

本專案採 [MIT 授權](LICENSE)。[第三方聲明](THIRD_PARTY_NOTICES.md)列出隨附元件及其授權。
