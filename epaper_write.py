#!/usr/bin/env python3
"""400x300 の画像を Santek EZ Sign (SE0420, 4.2インチ, 2色) に PaSoRi/nfcpy で書き込む。

プロトコル (相互運用のための解析結果):

  標準コマンド (ISO7816):
    SELECT (00 A4 ..) : NDEF アプリを選択
    VERIFY (00 20 ..) : 認証コードを送って書き込みを許可させる

  独自コマンド (CLA=F0。命令バイト D8/D2/D4 は Santek 独自で、解析で判明した割当。
  D2 に一般的な「書き込み」の意味があるわけではない):
    F0 D8 : 読み出し (read。前処理で機器情報の取得などに使う)
    F0 D2 : フレームバッファへの書き込み (write)
    F0 D4 85 : リフレッシュ (画面更新)

  書き込み手順:
    SELECT -> 前処理 (F0 D8 / 00 D1) -> VERIFY
      -> F0 D2 (write) で画像を 250 バイトずつ送る (P1P2 = チャンク番号, 圧縮なし)
      -> F0 D4 85 でリフレッシュ

  画像は 1bpp プレーン (400x300, MSB 先頭, ビット 0 = 黒)。

使い方:
  python3 epaper_write.py image.png [--black1] [--mirror] [--flip]
EZ Sign をリーダーに載せ、完了まで動かさないこと。
"""
import argparse
import time

import nfc
from PIL import Image

W, H = 400, 300
STRIDE = W // 8

# 認証コード。機種固定の値でユーザ秘密ではない。
VERIFY_APDU = "002000010420091210"


def build_plane(png, black_is_one, mirror, flip):
    """画像を 1bpp プレーンに変換する (MSB 先頭, 50 バイト/行, ビット 0 = 黒)。"""
    im = Image.open(png).convert("RGB").resize((W, H))
    px = im.load()
    rows = range(H - 1, -1, -1) if flip else range(H)
    data = bytearray()
    for y in rows:
        for xb in range(STRIDE):
            b = 0
            for i in range(8):
                x = xb * 8 + i
                if mirror:
                    x = W - 1 - x
                r, g, bl = px[x, y]
                lum = 0.3 * r + 0.59 * g + 0.11 * bl
                is_black = lum < 128
                bit = 1 if (is_black == black_is_one) else 0
                b = (b << 1) | bit
            data.append(b)
    return bytes(data)


def tx(tag, apdu_hex, label, to=3.0, tries=3):
    # NFC の通信は一時的に応答を取りこぼすことがあるので、数回まで再送する。
    last = None
    for attempt in range(tries):
        try:
            r = tag.transceive(bytes.fromhex(apdu_hex), timeout=to)
            sw = r[-2:].hex()
            head = apdu_hex if len(apdu_hex) <= 24 else apdu_hex[:24] + ".."
            print(f"  {label:20} {head} -> SW={sw}"
                  + (f" data={r[:-2].hex()}" if len(r) > 2 else ""))
            return sw
        except Exception as e:
            last = e
            if attempt < tries - 1:
                time.sleep(0.3)
    raise last


def write_image(tag, plane):
    tx(tag, "00A4040007D2760000850101", "SELECT")
    for apdu, lbl in [("F0D801FE050000000000", "init F0D801FE"),
                      ("00D1000000", "init 00D1"),
                      ("F0D8000005000000000E", "read info"),
                      (VERIFY_APDU, "VERIFY")]:
        try:
            tx(tag, apdu, lbl)
        except Exception:
            pass
    # F0 D2 で生書き込み: プレーンを 250 バイトずつ送る (P1P2 = チャンク番号)。
    off = idx = 0
    while off < len(plane):
        chunk = plane[off:off + 250]
        apdu = f"F0D2{idx:04X}{len(chunk):02X}" + chunk.hex()
        if tx(tag, apdu, f"chunk#{idx}") != "9000":
            print(f"  chunk {idx} 失敗")
            return False
        off += len(chunk)
        idx += 1
        # チャンク間ペーシング。無停止で連射するとコントローラが取りこぼし、
        # 途中のチャンクで transceive がタイムアウトも効かず固まることがある。
        time.sleep(0.03)
    print(f"  {idx} チャンク送信")
    sw = tx(tag, "F0D4850000", "REFRESH")
    ok = sw in ("9000", "009000")
    print("  => " + ("リフレッシュ OK" if ok else f"refresh SW={sw}"))
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("png")
    ap.add_argument("--black1", action="store_true", help="黒 = ビット 1 (既定はビット 0)")
    ap.add_argument("--mirror", action="store_true", help="左右反転")
    ap.add_argument("--flip", action="store_true", help="上下反転")
    args = ap.parse_args()

    plane = build_plane(args.png, args.black1, args.mirror, args.flip)
    print(f"plane={len(plane)}B")

    clf = nfc.ContactlessFrontend("usb")
    print(f"reader: {clf.device}")
    print("EZ Sign をリーダーに載せてください (最大60秒待機)...")
    deadline = time.time() + 60

    def on_connect(tag):
        print(f"tag: {tag}")
        write_image(tag, plane)
        return False

    try:
        clf.connect(rdwr={"on-connect": on_connect},
                    terminate=lambda: time.time() > deadline)
    finally:
        clf.close()


if __name__ == "__main__":
    main()
