# rcs380-epaper-writer

Santek EZ Sign (NFC 電子ペーパー) を、PC から Sony PaSoRi RC-S380 で書き換えるための非公式ツール群。
当日の予定を1日タイムラインとして表示するカレンダー用途を想定している。

対象機種: Santek EZ Sign SE0420 (4.2 インチ, 2 色)
確認済みリーダー: Sony PaSoRi RC-S380

## なぜこれを作ったか (RC-S380 対応)

Santek 公式の Windows アプリは NFC リーダーとして RC-S300 を推奨しており、一世代前の RC-S380 では書き込めない。
そこで EZ Sign が使う NFC 上のコマンドを解析し、nfcpy から直接叩くことで RC-S380 でも書き込めるようにした。

## 構成

- `epaper_write.py` : 400x300 の画像を EZ Sign に書き込む
- `epaper_calendar.py` : 当日予定を 400x300 2 色の 1 日タイムラインに描画
- `epaper_detect.py` : タグの NFC 規格を判定する診断ツール

## 必要なもの

- Python 3, nfcpy, Pillow
- Sony PaSoRi RC-S380
- Linux では nfcpy がデバイスにアクセスできるよう権限設定が必要
  (udev ルール、または一時的に chmod でデバイスノードを開放)

```
pip install -r requirements.txt
```

## 使い方

画像を1枚表示する:

```
python3 epaper_write.py image.png
```

EZ Sign をリーダーの上に置いて静止させると、書き込み後に画面が更新される。

画像は自動で 400x300 に縮小し、輝度しきい値で 2 値化する。
既定はビット 0 = 黒。必要に応じて black1 / mirror / flip の各オプションを指定。

当日カレンダーを描いて表示する:

```
python3 epaper_calendar.py --demo -o calendar.png   # ダミー予定の表示用画像 calendar.png を生成
python3 epaper_write.py calendar.png                # その画像を EZ Sign に書き込む
```

自分の予定から描くには、予定を JSON で用意して events に渡す。
各要素は title, start, end, allDay を持ち、start と end は ISO8601 で書く。

```
python3 epaper_calendar.py --events events.json --today 2026-07-10 -o calendar.png
python3 epaper_write.py calendar.png
```

予定 JSON の例:

```
[
  {"title": "朝会", "start": "2026-07-10T09:30:00", "end": "2026-07-10T10:00:00", "allDay": false},
  {"title": "健康診断", "start": "2026-07-10T00:00:00", "end": "2026-07-10T00:00:00", "allDay": true}
]
```

予定データをどこから用意するかは利用者に任せる。カレンダーサービスからの取得は
環境や規約に依存するため、本リポジトリには含めていない。

## プロトコル概要 (相互運用のための解析結果)

EZ Sign SE0420 は NFC-A / ISO14443-4 (ISO-DEP) で応答する。書き込みは APDU 形式のコマンドで行う。
コマンドを送ると、末尾2バイトの結果コードつきで応答が返る。9000 が成功。

- SELECT (標準コマンド): NDEF アプリケーションを選択
- 前処理 (独自コマンド): セッション初期化
- VERIFY (標準の認証コマンド): 機種固定のコードを送って書き込みを許可させる
- フレームバッファ書き込み (独自コマンド): 400x300 の 1bpp プレーン (50 バイト/行,
  MSB 先頭, ビット 0 = 黒) を 250 バイトずつのチャンクで送る (圧縮なし)
- リフレッシュ (独自コマンド): 画面を再描画

具体的な APDU の16進値は epaper_write.py の実装 (送信しているコマンド文字列) を参照のこと。

## 注意・免責

- 本プロジェクトは非公式で、Santek 社・Sony 社とは無関係である。
- 解析は相互運用を目的としている。
- 機器やデータの破損について責任は負わない。自己責任で利用すること。

## 商標について

- "EZ Sign"および"Santek"は San Technology, Inc. の商標である。
- "PaSoRi"は Sony グループの商標である。
- 本リポジトリでのこれらの名称の使用は、対応する実在製品を指し示すためであり、権利者による許諾・提携・推奨を意味しない。

## ライセンス

MIT License (LICENSE 参照)
