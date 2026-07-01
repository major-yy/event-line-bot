# Personal Weekly Event LINE Bot

自分ともう1人だけに、毎週1都3県のイベント候補をLINEで送るための最小構成です。

## Flow

1. `config/sources.json` の巡回先を読む
2. `scripts/collect_events.py` がイベント候補を集める
3. `scripts/render_line_message.py` がLINE用の短い文面にする
4. `scripts/send_line_push.py` が2人のLINE userIdへPush送信する
5. `scripts/mark_sent.py` が送信済み履歴を保存する

## Local dry run

```powershell
python scripts/collect_events.py
python scripts/render_line_message.py --limit 10
python scripts/send_line_push.py --dry-run
python scripts/mark_sent.py
```

`data/sent_history.json` に通知済みイベントを保存します。ここに入ったイベントは、次回以降のLINE文面から外れます。

## LINE secrets

GitHub Actionsで使う場合は、Repository secretsに以下を入れます。

- `LINE_CHANNEL_ACCESS_TOKEN`
- `LINE_USER_IDS`

`LINE_USER_IDS` はカンマ区切りです。

```text
Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx,Uyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy
```

## Get userIds

友だち追加済みでも、Push送信には各ユーザーの `userId` が必要です。

1. LINE DevelopersでWebhookを有効化する
2. ローカルで受け口を起動する

```powershell
$env:LINE_CHANNEL_SECRET="..."
python scripts/webhook_userid_receiver.py --port 8787
```

3. ngrokやcloudflaredで `http://127.0.0.1:8787` を公開する
4. 公開URLをLINE DevelopersのWebhook URLに設定する
5. 自分ともう1人が公式アカウントへ何かメッセージを送る
6. ターミナルに表示された2つの `user_id` を `LINE_USER_IDS` に入れる

## Weekly automation

`.github/workflows/weekly-events.yml` は毎週金曜8:00 JSTに実行されます。

送信後、`data/sent_history.json` を自動コミットします。これにより、一度LINEに出したイベントは次回以降に再通知されません。

初回テストはGitHub Actionsの `Run workflow` から手動実行してください。

## Source policy

最初は公式観光サイトとよく行く施設だけに絞っています。候補が少ない週だけ、民間イベントサイトや検索APIを追加するのが安全です。
