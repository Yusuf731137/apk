[app]

# عنوان التطبيق الظاهر على الهاتف
title = My Kivy App

# اسم الحزمة الفريد
package.name = mykivyapp
package.domain = org.test

# الملفات المضمنة في المشروع (لاحظ أننا أضفنا py و المجلدات الظاهرة في صورتك)
source.include_exts = py,png,jpg,kv,atlas,txt,json
source.include_dir = core,data,scripts,services,tests,translations,ui

# (هام جداً): اسم ملف بايثون الرئيسي الذي يشغل التطبيق
# إذا سميت ملفك main.py اتركها main.py، أما إذا بقي اسمه app.py فاكتبه هنا:
main.filename = app.py

# متطلبات المشروع (مكتبة بايثون و Kivy)
requirements = python3,kivy

# اتجاه الشاشة (عمودي)
orientation = portrait

android.permissions = INTERNET

[buildozer]
log_level = 2
warn_on_root = 1
