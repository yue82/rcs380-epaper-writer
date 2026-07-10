#!/usr/bin/env python3
"""EZ Sign / NFC タグの規格判定用スクリプト。

RC-S380 (PaSoRi) で EZ Sign をかざし、どの NFC 規格で応答するかを見る。
- 106A (ISO14443A) で応答すれば、RC-S380 で通信できる
- どれも応答しなければ ISO15693 (NFC-V) の可能性が高く、RC-S380 では通信できない

使い方:
    source ~/nfc-venv/bin/activate
    python3 epaper_detect.py
EZ Sign をリーダー中央にかざした状態で実行する。
"""

import nfc
from nfc.clf import RemoteTarget


def main():
    clf = nfc.ContactlessFrontend("usb")
    print(f"reader: {clf.device}")

    # RC-S380 が sense できる技術を順に試す。
    # NFC-V (ISO15693) は RC-S380 では sense 対象外なのでここには含めない。
    techs = [
        ("106A (ISO14443A / NFC-A)", RemoteTarget("106A")),
        ("106B (ISO14443B / NFC-B)", RemoteTarget("106B")),
        ("212F (FeliCa)", RemoteTarget("212F")),
        ("424F (FeliCa)", RemoteTarget("424F")),
    ]

    found = False
    for label, target in techs:
        result = clf.sense(target, iterations=3, interval=0.1)
        if result is not None:
            found = True
            print(f"\n応答あり: {label}")
            print(f"  sens_res / sensf_res: {result}")
            for attr in ("sdd_res", "sel_res", "sensb_res", "sensf_res"):
                val = getattr(result, attr, None)
                if val is not None:
                    print(f"  {attr}: {val.hex()}")
        else:
            print(f"応答なし: {label}")

    clf.close()

    print()
    if found:
        print("=> ISO14443/FeliCa 系で応答。RC-S380 で通信できる。")
        print("   sel_res(SAK)/sens_res(ATQA) を記録しておくとチップ特定に使える。")
    else:
        print("=> どの技術でも応答なし。ISO15693 (NFC-V) の可能性が高い。")
        print("   その場合 RC-S380 では通信できない。NFC-V 対応リーダーが必要。")


if __name__ == "__main__":
    main()
