import sys, json
import pymupdf
doc = pymupdf.open(sys.argv[1])
pages = []
for page in doc:
    W, H = page.rect.width, page.rect.height
    blocks = [b for b in page.get_text('blocks') if b[6] == 0 and b[4].strip()]
    body = [b for b in blocks if b[1] > 38 and b[3] < H - 25]
    wide = sorted([b for b in body if (b[2] - b[0]) > W * 0.55], key=lambda b: b[1])
    cuts = [b[1] for b in wide]
    def band(b):
        return sum(1 for c in cuts if b[1] >= c - 0.5)
    def col(b):
        if (b[2] - b[0]) > W * 0.55:
            return -1
        return int(min(2, max(0, (b[0] - 20) // ((W - 40) / 3))))
    ordered = sorted(body, key=lambda b: (band(b), col(b), b[1], b[0]))
    pages.append('\n'.join(b[4].rstrip() for b in ordered))
open(sys.argv[2], 'w', encoding='utf-8').write('\f'.join(pages))
print(len(pages))
