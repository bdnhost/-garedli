# מסמך דרישות מוצר (PRD) - מגרדת רשת אוטונומית מבוססת AI

**שם המוצר:** Manus-ScrapeX: מגרדת רשת אוטונומית מבוססת AI
**גרסה:** 1.0
**תאריך:** 15 בנובמבר 2025
**מחבר:** Manus AI

---

## 1. היסטוריית גרסאות

| גרסה | תאריך | תיאור השינוי | מחבר |
| :--- | :--- | :--- | :--- |
| 1.0 | 15.11.2025 | יצירת מסמך ראשוני. הגדרת ארכיטקטורת סוכני AI. | Manus AI |

---

## 2. מבוא

### 2.1. חזון ומטרת המוצר

החזון של **Manus-ScrapeX** הוא ליצור את פתרון גירוד הרשת **האמין והאוטונומי ביותר** הקיים, המסוגל לגרוד כל סוג של מידע מכל אתר אינטרנט, ללא תלות במורכבותו הטכנולוגית או במנגנוני ההגנה שלו.

**מטרת העל:** להגיע לשיעור הצלחה של **100%** בגירוד נתונים מובנים, תוך מזעור התלות בתחזוקה ידנית של קוד הגירוד.

### 2.2. קהל יעד

*   מדעני נתונים (Data Scientists) ומהנדסי למידת מכונה (ML Engineers) הזקוקים למאגרי נתונים נקיים ועדכניים.
*   אנליסטים עסקיים וצוותי מודיעין תחרותי (Competitive Intelligence) הזקוקים למידע בזמן אמת.
*   מפתחי תוכנה הזקוקים לפתרון גירוד גמיש וסקיילבילי.

---

## 3. יעדים ומדדי הצלחה (KPIs)

המוצר יוגדר כהצלחה אם יעמוד ביעדים הבאים:

| יעד | מדד הצלחה (KPI) | יעד כמותי |
| :--- | :--- | :--- |
| **אמינות הגירוד** | שיעור הצלחה בגירוד נתונים מובנים (Data Extraction Success Rate) | **100%** (מתוך מדגם של 1,000 אתרים מורכבים) |
| **איכות הנתונים** | שיעור שגיאות וולידציה (Validation Error Rate) | פחות מ-0.1% |
| **אוטונומיה** | שיעור התאמות אוטומטיות לשינויי סכמה (Schema Drift Adaptation Rate) | 95% |
| **ביצועים** | זמן ממוצע לגירוד דף (Average Page Scrape Time) | פחות מ-3 שניות (לאתרים דינמיים) |

---

## 4. דרישות פונקציונליות (Functional Requirements)

| ID | דרישה | תיאור |
| :--- | :--- | :--- |
| **FR-001** | **גירוד אדפטיבי** | המערכת תדע לבחור אוטומטית את כלי הגירוד המתאים ביותר (HTTP Request, Headless Browser) על בסיס ניתוח ראשוני של ה-URL. |
| **FR-002** | **עקיפת Anti-Bot** | המערכת תדע לזהות ולעקוף מנגנוני הגנה נפוצים (Cloudflare, DataDome, CAPTCHA) באמצעות טכניקות הסוואה ופתרון מבוסס AI. |
| **FR-003** | **מיצוי סמנטי** | המערכת תאפשר למשתמש להגדיר את סכמת הנתונים הרצויה (למשל, "מחיר", "כותרת") באמצעות שפה טבעית, וה-AI ימצה את הנתונים בהתאם, גם אם מבנה ה-HTML משתנה. |
| **FR-004** | **וולידציה אוטומטית** | המערכת תבצע וולידציה אוטומטית לנתונים שנגרדו (בדיקת סוג נתונים, טווחים, עקביות לוגית) ותסמן נתונים חשודים. |
| **FR-005** | **ניהול משאבים** | המערכת תנהל מאגר פרוקסי מסתובב (Rotating Proxy Pool) ותחליף כתובות IP באופן אוטונומי במקרה של חסימה. |
| **FR-006** | **ממשק API** | המערכת תספק ממשק RESTful API פשוט להזנת URL וקבלת נתונים מובנים (JSON) כפלט. |

---

## 5. ארכיטקטורה ומפרט טכני

הארכיטקטורה המוצעת היא **מערכת מרובת סוכנים (Multi-Agent System)** היברידית, המשלבת את היתרונות של Frameworks לגירוד בקנה מידה גדול עם יכולות קבלת החלטות ולמידה של AI.

### 5.1. ספריות ליבה נבחרות

| תפקיד | כלי מומלץ | סיבה לבחירה |
| :--- | :--- | :--- |
| **Framework ליבה** | **Scrapy** (Python) | סקיילביליות, אסינכרוניות, ניהול תורים ו-Pipelines מובנה [1]. |
| **רינדור JavaScript** | **Playwright** (Python/Node.js) | API מודרני, תמיכה בריבוי דפדפנים (Chromium, Firefox, WebKit), עדיף על Selenium [2]. |
| **ניתוח HTML** | **Beautiful Soup** (Python) | קלות שימוש ומהירות לניתוח ה-HTML המרונדר ומיצוי נתונים ספציפיים [3]. |
| **AI/LLM** | **מודל LLM מתקדם** | קבלת החלטות (Dispatcher), מיצוי סמנטי (Extractor), ופתרון אתגרים (Anti-Bot). |

### 5.2. ארכיטקטורת מערך סוכני AI

המערכת מורכבת מארבעה סוכנים אוטונומיים הפועלים במחזוריות:

#### 5.2.1. סוכן ניהול ובחירת אסטרטגיה (Dispatcher Agent)
*   **תפקיד:** מקבל URL, מבצע בדיקה ראשונית (האם סטטי או דינמי), ומחליט על נתיב הגירוד (Scrapy או Playwright).
*   **מודל קבלת החלטות:** מודל סיווג (Classification Model) המאומן על מאפייני אתרים (נוכחות JavaScript, קוד סטטוס, כותרות HTTP).

#### 5.2.2. סוכן עקיפת חסימות (Anti-Bot Agent)
*   **תפקיד:** מנטר את תהליך הגירוד, מזהה חסימות (IP Block, CAPTCHA), ומפעיל טקטיקות עקיפה.
*   **טקטיקות:**
    *   **הסוואה:** שינוי User-Agent, שימוש ב-Playwright עם טביעת אצבע אנושית (Fortified Headless).
    *   **פתרון אתגרים:** שימוש במודל ראייה (Vision Model) לפתרון CAPTCHA.
    *   **ניהול IP:** הוראה למאגר הפרוקסי להחליף כתובת IP.

#### 5.2.3. סוכן ניתוח ומיצוי נתונים (Extractor Agent)
*   **תפקיד:** אחראי על מיצוי הנתונים מה-HTML המרונדר לפורמט מובנה.
*   **שיטה:** שימוש ב-LLM לזיהוי סמנטי של הנתונים הנדרשים (למשל, "האלמנט בדף המייצג את המחיר") במקום הסתמכות על Selectors קשיחים.

#### 5.2.4. סוכן וולידציה ובקרת איכות (Validator Agent)
*   **תפקיד:** הבטחת איכות הנתונים.
*   **פעולה:** בדיקת עקביות, שלמות וסוג נתונים. במקרה של כשל, מפעיל לולאת משוב (Feedback Loop) המורה ל-Dispatcher לנסות אסטרטגיה חלופית.

### 5.3. דיאגרמת ארכיטקטורה

להלן דיאגרמה הממחישה את זרימת העבודה בין הסוכנים וכלי הליבה:

![דיאגרמת ארכיטקטורת מערך סוכני AI לגירוד רשת](https://private-us-east-1.manuscdn.com/sessionFile/wWW5UI6AlYUg3Xnwp4bBpz/sandbox/iP3RD8Iq4r7YtdTJ2GItsT-images_1763219147428_na1fn_L2hvbWUvdWJ1bnR1L2FpX3NjcmFwZXJfYXJjaGl0ZWN0dXJl.png?Policy=eyJTdGF0ZW1lbnQiOlt7IlJlc291cmNlIjoiaHR0cHM6Ly9wcml2YXRlLXVzLWVhc3QtMS5tYW51c2Nkbi5jb20vc2Vzc2lvbkZpbGUvd1dXNVVJNkFsWVVnM1hud3A0YkJwei9zYW5kYm94L2lQM1JEOElxNHI3WXRkVEoyR0l0c1QtaW1hZ2VzXzE3NjMyMTkxNDc0MjhfbmExZm5fTDJodmJXVXZkV0oxYm5SMUwyRnBYM05qY21Gd1pYSmZZWEpqYUdsMFpXTjBkWEpsLnBuZyIsIkNvbmRpdGlvbiI6eyJEYXRlTGVzc1RoYW4iOnsiQVdTOkVwb2NoVGltZSI6MTc5ODc2MTYwMH19fV19&Key-Pair-Id=K2HSFNDJXOU9YS&Signature=PZ96nHJdUPa4mPEszXOKKuw3l4zj2oxI8rsRCQAn5Zi4o0Nh-20nmRqk3CLlDEc8vdV0VfCPBrK1aUl4aMDP9fkG-jWkpxR2~h8hmfuYLQFvtWy1PkmLFmSWbSPN0WGMKjwZkEoxRY4-Q~2Oe6d5B5Xzvyi7hRTtpNGVdPxM~FfEFq-7iacAQ8Keukc5xIjFRIP6QsntDpo0rdPTd8AfYoRJbgcf-kGyUqy6VkZDz5On-BL1GUPKfbPdZcMnqHCFFxwlEzpShlTc3l56R9e9BIKui5gvrZyqtI9FRkk4zID4NTEXdmbsa33O-8AWRwMvgQ9FZ-1p1C-TBP1dY7V~MQ__)

---

## 6. דרישות לא פונקציונליות (Non-Functional Requirements)

| קטגוריה | דרישה |
| :--- | :--- |
| **סקיילביליות** | המערכת תהיה מסוגלת לטפל במיליוני בקשות גירוד ביום באמצעות ארכיטקטורה מבוססת תורים (Queues) ו-Microservices. |
| **אבטחה** | כל התקשורת עם מאגר הפרוקסי תהיה מוצפנת (HTTPS). המערכת תפעל בסביבה מבודדת (Sandboxed Environment). |
| **תחזוקה** | קוד הגירוד יהיה מופרד לוגית מקוד ה-AI, מה שיאפשר עדכון קל של ספריות הגירוד (Scrapy, Playwright) ללא פגיעה במודלי ה-AI. |
| **למידה** | המערכת תכלול מנגנון למידה מתמשכת (Continuous Learning) המשתמש בנתוני כשל (Failed Scrapes) כדי לאמן מחדש את מודל ה-Dispatcher ואת טקטיקות ה-Anti-Bot. |

---

## 7. סיכום ומסקנות

השגת יעד ה-**100%** דורשת מעבר מגירוד מבוסס כללים (Rule-Based) לגירוד מבוסס **אינטליגנציה ואדפטיביות**. ארכיטקטורת מערך הסוכנים המוצעת (Manus-ScrapeX) מספקת את המסגרת הנדרשת לכך, על ידי פיצול המשימה המורכבת לתפקידים אוטונומיים ומתמחים.

---

## 8. רפרנסים (References)

[1] Scrapy: A Fast and Powerful Scraping and Web Crawling Framework. *Scrapy Documentation*.
[2] Playwright vs Puppeteer: Which Web Scraping Tool Wins. *PromptCloud Blog*.
[3] Beautiful Soup Documentation. *Crummy.com*.
