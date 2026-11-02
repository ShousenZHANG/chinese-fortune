"""焦氏易林查林：按本卦、之卦取两个版本的林辞，原文与段号并列，不作解读。

两个版本都来自维基文库固定修订（knowledge/books）：
- yilin：《四部叢刊》景北京圖書館藏元刊本，十六卷，附闕名注；维基文库为扫描页逐页录入，校对等级多为 1（未校对）。
- yilin_siku：文淵閣《四庫全書》本，维基文库分四卷录入，六十四卦齐全，未逐页校图。

一卦变六十四，共四千零九十六林。两本用字、异文不同时并列给出，不替原文择一。

CLI:
    python yilin_lookup.py --from 乾 --to 坤
    python yilin_lookup.py --from 乾          # 乾之六十四林
"""
from __future__ import annotations

import argparse
import sys
from functools import lru_cache

from classical_search import chapter_passages
from utils import __version__, ensure_utf8_stdio, error_envelope, json_print

# 文王卦序，繁体。
GUA = ('乾', '坤', '屯', '蒙', '需', '訟', '師', '比', '小畜', '履', '泰', '否', '同人', '大有', '謙', '豫',
       '隨', '蠱', '臨', '觀', '噬嗑', '賁', '剝', '復', '無妄', '大畜', '頤', '大過', '坎', '離', '咸', '恆',
       '遯', '大壯', '晉', '明夷', '家人', '睽', '蹇', '解', '損', '益', '夬', '姤', '萃', '升', '困', '井',
       '革', '鼎', '震', '艮', '漸', '歸妹', '豐', '旅', '巽', '兌', '渙', '節', '中孚', '小過', '既濟', '未濟')
# 两本与简体输入里出现的异写，逐字换成上表用字。
CHAR_VARIANTS = str.maketrans({
    '乹': '乾', '无': '無', '旡': '無', '恒': '恆', '遁': '遯', '晋': '晉', '頥': '頤', '颐': '頤', '觧': '解',
    '㢲': '巽', '兊': '兌', '兑': '兌', '剥': '剝', '离': '離', '讼': '訟', '师': '師', '谦': '謙', '随': '隨',
    '蛊': '蠱', '临': '臨', '观': '觀', '贲': '賁', '复': '復', '过': '過', '壮': '壯', '损': '損', '渐': '漸',
    '归': '歸', '丰': '豐', '豊': '豐', '涣': '渙', '节': '節', '济': '濟', '済': '濟',
    '旣': '既', '𢘆': '恆', '𫎇': '蒙', '遘': '姤', '𣈆': '晉', '㤗': '泰', '妺': '妹', '暌': '睽',
})
# 四库本、四部叢刊本里实际出现的异写卦名（切分时当作卦名）。
SOURCE_SPELLINGS = frozenset({'乹', '无妄', '旡妄', '恒', '遁', '晋', '頥', '觧', '㢲', '兊', '兑', '剥', '离',
                              '𫎇', '旣濟', '𢘆', '遘', '𣈆', '㤗', '歸妺', '暌'})
# Section name for a lin whose page label conflicts with the order (pages out of order in the transcription).
UNPLACED = '（标题与卦序冲突，归属未定）'
EDITIONS = {'yilin': '四部叢刊景元刊本（附闕名注）', 'yilin_siku': '文淵閣四庫全書本'}
SBCK_CHAPTERS = tuple(f'c{i:03}' for i in range(1, 17))
SIKU_CHAPTERS = tuple(f'c{i:03}' for i in range(1, 5))


def canon(name: str) -> str | None:
    name = name.strip().translate(CHAR_VARIANTS)
    return name if name in GUA else None


@lru_cache(maxsize=2)
def _index(book: str) -> dict[str, dict]:
    """section 「本卦之之卦」 -> {verse passage, commentary passages}."""
    chapters = SBCK_CHAPTERS if book == 'yilin' else SIKU_CHAPTERS
    index: dict[str, dict] = {}
    for chapter in chapters:
        for passage in chapter_passages(f'{book}:{chapter}'):
            entry = index.setdefault(passage['section'], {'verse': None, 'notes': [], 'also': []})
            record = {'passage_id': passage['passage_id'], 'sha256': passage['sha256'], 'text': passage['text'],
                      **({'attribution': passage['attribution']} if passage.get('attribution') else {})}
            if passage['layer'] == 'commentary':
                entry['notes'].append(record)
            elif entry['verse'] is None:
                entry['verse'] = record
            else:  # the transcription labels two lins alike; show both, do not pick
                entry['also'].append(record)
    return index


def lin(ben: str, zhi: str) -> dict:
    key = f'{ben}之{zhi}'
    versions = []
    for book, edition in EDITIONS.items():
        entry = _index(book).get(key)
        if entry and entry['verse']:
            versions.append({'book': book, 'edition': edition, **entry['verse'], 'notes': entry['notes'],
                             **({'same_label_also': entry['also']} if entry['also'] else {})})
        else:
            unplaced = _index(book).get(f'{ben}{"之"}{UNPLACED}')
            row: dict = {'book': book, 'edition': edition, 'passage_id': None, 'text': None,
                         'reason': '这个版本的转录缺这一林，或未能切分'}
            if unplaced:
                found = [unplaced['verse'], *unplaced['also']]
                row['reason'] = (f'这一林在本版转录中没有确定位置：本卦另有 {len(found)} 段林辞的原页标题与卦序冲突'
                                 '（页序错乱），归属未定，见 unplaced_in_this_ben，不替原文指定')
                row['unplaced_in_this_ben'] = found
            versions.append(row)
    for v in versions:
        if v.get('attribution'):
            v['attribution_note'] = v['attribution']['note']
    texts = {v['text'] for v in versions if v['text']}
    return {'ben': ben, 'zhi': zhi, 'key': key, 'versions': versions,
            'same_text': len(texts) == 1 and all(v['text'] for v in versions)}


EPILOG = """Top-level JSON keys on stdout (UTF-8):
  ok tool version query lin (one) | lins (all 64 of one ben) boundary

On error: {"ok": false, "error": ..., "message": ...} and exit 1."""


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    parser = argparse.ArgumentParser(description='焦氏易林查林：本卦之某卦的林辞，两个版本并列', epilog=EPILOG,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--from', dest='ben', required=True, help='本卦名，如 乾、小畜、既济（简繁皆可）')
    parser.add_argument('--to', dest='zhi', help='之卦名；省略时列出本卦的六十四林')
    args = parser.parse_args(argv)
    ben = canon(args.ben)
    zhi = canon(args.zhi) if args.zhi else None
    if ben is None or (args.zhi and zhi is None):
        bad = args.ben if ben is None else args.zhi
        json_print(error_envelope('yilin', 'invalid_input', f'不是六十四卦名：{bad}'))
        return 1
    out = {'ok': True, 'tool': 'yilin', 'version': __version__, 'query': {'from': ben, 'to': zhi},
           'boundary': '只给两个版本的原文与段号；林辞是汉代占辞，不据此预测个人事件，异文并列不择一。'}
    if zhi:
        out['lin'] = lin(ben, zhi)
    else:
        out['lins'] = [lin(ben, other) for other in GUA]
    json_print(out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
