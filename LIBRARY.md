# The official library

Vanguard answers from what's in `library/`. Add official **public** documents there as `.pdf`, `.txt` or `.md` — Vanguard indexes them automatically (Me → Reload library, or restart).

U.S. Army publications and federal law are works of the U.S. Government and free to use. Download publications from the **Army Publishing Directorate** (armypubs.army.mil — search by the publication number) or the other official sites below. Use the newest version.

## Automatic downloads
`python tools/fetch_library.py` (needs internet once) adds:
- the full **UCMJ** (10 U.S.C. chapter 47) from govinfo.gov
- the **Summary of the Thrift Savings Plan** (TSPBK08) from tsp.gov
- the public **Army publications** from armypubs.army.mil: TC 7-21.13, AR 670-1, DA PAM 670-1, AR 600-20, AR 600-25, TC 3-21.5, FM 7-22, AR 530-1, ATP 4-02.2, TC 3-21.76 (Ranger Handbook), AR 600-52 (SHARP Program), FM 6-22 (Developing Leaders), ATP 6-22.1 (The Counseling Process), ATP 4-25.12 (Unit Field Sanitation Teams), TC 3-22.9 (Rifle and Carbine), TC 4-02.3 (Field Hygiene and Sanitation), TC 3-21.75 (Warrior Ethos and Soldier Combat Skills) and AR 621-5 (Army Continuing Education System). Only copies marked *approved for public release* are taken — never anything behind a CAC login.

To see whether the Army has published a newer edition of anything installed (downloads nothing): `python tools/fetch_library.py --check`.

Not automatic: **TC 3-25.26** (land navigation) is CAC-restricted on armypubs now, and **TC 4-02.1** (first aid) is no longer listed as active.

Some official sites block automated downloads (dfas.mil, militarypay.defense.gov, and armypubs.army.mil during maintenance). Save those PDFs from a browser into `library/`, then run `python tools/fetch_library.py` again: it converts every PDF to text **once, on that computer**, so devices running Vanguard never need a PDF reader.

## Start with these

| Publication | What it covers | Where |
|---|---|---|
| TC 7-21.13, *The Soldier's Guide* | Creeds, values, customs, history, basic Soldier knowledge | armypubs.army.mil |
| AR 670-1, *Wear and Appearance of Army Uniforms and Insignia* | Uniform, grooming, tattoo and appearance rules | armypubs.army.mil |
| DA PAM 670-1, *Guide to the Wear and Appearance of Army Uniforms and Insignia* | Exact placement, measurements, diagrams | armypubs.army.mil |
| AR 600-20, *Army Command Policy* | Chain of command, EO, SHARP, relationships | armypubs.army.mil |
| AR 600-25, *Salutes, Honors, and Courtesies* | Customs and courtesies | armypubs.army.mil |
| TC 3-21.5, *Drill and Ceremonies* | Drill | armypubs.army.mil |
| FM 7-22, *Holistic Health and Fitness* | PT, nutrition, sleep, mental readiness | armypubs.army.mil |
| TC 3-25.26, *Map Reading and Land Navigation* | Land nav | armypubs.army.mil |
| TC 4-02.1, *First Aid* | First aid | armypubs.army.mil |
| AR 530-1, *Operations Security* | OPSEC | armypubs.army.mil |
| The UCMJ (10 U.S.C. chapter 47) | Military law | automatic (govinfo.gov) |
| DFAS *Understanding your LES* / LES guide | What every line on the pay statement means | dfas.mil (save from a browser) |
| Blended Retirement System guides | Retirement and TSP for service members | militarypay.defense.gov (save from a browser) |
| Manual for Courts-Martial (current edition) | UCMJ articles explained | jsc.defense.gov |

## Jobs (MOS)
Use **public** job descriptions only (for example, the career pages on goarmy.com saved as text). The Army's full occupational manual (DA PAM 611-21) is restricted to CAC holders — do **not** add it.

## Never add
Anything marked CUI, FOUO, classified, or restricted-distribution; anything from behind a CAC login; unit-specific SOPs, rosters or locations.

## Books (separate from the library)
Free public-domain books — Army history, founding documents and classics — live in `books/` (see `books/README.md`).
They're for reading in Study → 📚 Books; Ask never answers from them.
