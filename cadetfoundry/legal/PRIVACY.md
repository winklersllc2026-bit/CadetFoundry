# Cadet Foundry — Privacy notice

Version 2026-10-12 · Questions: **support@cadetfoundry.org**

Cadet Foundry is a free community project — **the Cadet Foundry project.** This notice is for instructors, schools, Cadets and parents. The short version: **everything stays on the instructor's computer, and the Cadet Foundry project never receives any of it.**

## Where data is kept
All of Cadet Foundry's data is stored in one folder on the computer it runs on — the instructor's laptop, or the USB drive Cadet Foundry runs from. Cadets' phones and tablets only show pages; the only things their browser remembers are display settings (text size, night mode, the last Learn section, whether the tour was shown). There is **no Cadet Foundry server, no cloud account, no tracking, no advertising, and no analytics.** The Cadet Foundry project can't see or copy anything in that folder.

## What is stored, and who can see it
- **Profile name and PIN.** The name shows on the sign-in screen (shortened on other devices). The PIN is stored only as a slow, salted hash.
- **Private files** — Ask chats, check-ins, notes, letters, logbook, address book. **Only that person** can open them — not the instructor, not the device owner, not the Cadet Foundry project. They're encrypted with that person's own key (AES-256-GCM, unlocked by their PIN).
- **Class records** — assigned lessons and scores, quizzes and exams, leadership scenarios, fitness and service hours. The Cadet and the instructor (with the Class PIN) can see them. They're encrypted with a separate per-Cadet class key.
- **Program data** — classes, roster details, lessons, pilot setup and feedback, survey answers. Instructors with the Class PIN can see them. They're sealed with the program key; survey answers carry no name.
- **Live class votes and live questions.** Instructors see **counts only**, never who. They're kept in memory during class only.

Cadet Foundry asks for a **name and a PIN** — no email, phone number, address, photo or birth date. Anything else is what a person chooses to type, and it stays in their own encrypted files.

## Who decides
The instructor's program and school decide how Cadet Foundry is used, how long records are kept, and when they are deleted. Cadet Foundry gives them the tools:
- **Delete profile** (Me) removes a person's own profile and every file in it.
- **End pilot** (Instructor → Reports → Pilot, in Pilot mode) removes every Cadet and parent profile and the pilot's class data, after the reports are saved.
- **Class report** and **pilot report** exports, which the instructor downloads on purpose.
- **Encrypted backups**, protected by a password the owner chooses.

## Ask is private — and not monitored
Nobody reads Cadets' Ask chats, including the instructor. Ask has a safety check that shows help numbers when a message sounds unsafe, but it **notifies no one.** A Cadet who is in danger should tell a trusted adult, or call or text **988** — in an emergency, **911**.

## Cadet flash drives
An instructor can give a Cadet Cadet Foundry on a flash drive to study at home. The drive holds **that Cadet's profile
only**, encrypted with their own PIN, plus the lessons they were given — never the Class PIN, the program's keys or
anyone else's data. When the drive is plugged into the instructor's computer, **class records** (the same ones the
instructor can already see) are brought in and new lessons go out. **Private files stay on the drive** and are never
copied. If a drive is lost, its files stay locked behind the Cadet's PIN; the instructor can make a new drive with the
class work last brought to class.

## No online AI
Cadet Foundry has **no online AI** and sends nothing to the internet. The only AI is an optional one that runs on the
instructor's own computer. Cadets' flash drives don't have it.

## The classroom network
When an instructor turns Cadet phones on, pages travel over that Wi-Fi network without HTTPS. Use a network only the class joins (WPA3 if possible), not open or guest Wi-Fi. Details for school IT are in SECURITY.md.

## The website
cadetfoundry.org sets **no cookies**, runs **no analytics**, and has **no accounts**. It is hosted by Cloudflare, whose servers keep the standard technical logs any website host keeps (such as IP addresses). Downloads come from a public GitHub page, under GitHub's own terms.

## Email
If you email support@cadetfoundry.org, your message is forwarded to the project's email inbox and used only to answer you. Please don't send student records or Cadets' private information by email.

## Children
Cadets are often under 18. Cadet Foundry is designed so that their information stays with their own program, on their instructor's computer, and never reaches the Cadet Foundry project.

## Changes and contact
This notice may be updated; the version date is at the top. Questions, deletion help or security reports: **support@cadetfoundry.org**.
