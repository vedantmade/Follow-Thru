# What a good extraction of meeting 2 looks like (use this to test your prompt)
Meeting date: 2026-11-21 (Saturday). Attendees: Rahul, Amit, Neha. Priya absent.

## Decisions (2), both conflict with memory
| topic | new decision | evidence | conflicts with (14 Nov) |
|---|---|---|---|
| database | Switch to MongoDB | T2, T3, T4 | PostgreSQL (Priya, T2/T5). Priya absent today. Impacts task "Set up Postgres schema" |
| launch date | Launch on December 5th | T5, T6 | December 10th (Rahul, T9). Impacts "Write launch blog post"? (due 30 Nov, after launch!) |

## Action items, one per pronoun case
| case | task | owner | deadline | confidence |
|---|---|---|---|---|
| named "you" + accept | Migrate user service to MongoDB driver | Amit | 2026-11-27 (Friday) | high (T7, T8) |
| unnamed "you" + accept | Build beta signup form on landing page | Neha | 2026-11-25 (Wednesday EOD) | high (T9, T10) |
| "he" | Check Razorpay refund flow before launch | Amit | null, "before launch", ask or use launch date | medium (T11) |
| Hinglish "I'll" | Send load-testing script | Rahul | 2026-11-22 ("kal" = tomorrow) | high (T12) |
| "we/someone" | Fix slow dashboard API | null | null | low, VAGUE (T13, T14) |
