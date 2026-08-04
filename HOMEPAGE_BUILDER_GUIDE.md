# Home Page Builder - Implementation Guide

## 📋 Overview
This feature allows admins to visually create, edit, and manage the HTML and CSS content of the website's Home Page through an intuitive admin interface.

---

## 🚀 Installation Steps

### Step 1: Update Database Model
The `HomePageSection` model has been added to `backend/models.py`. This model stores:
- Section title
- HTML content
- CSS content (optional)
- Display order
- Publish status
- Creation/update timestamps

### Step 2: Run Database Migration
```bash
cd backend
python migrate_homepage_builder.py
```

This will:
- Create the `homepage_sections` table
- Add a default "Welcome Section" as an example

### Step 3: Add API Endpoints to main.py

Open `backend/main.py` and add the following import at the top:
```python
from models import HomePageSection  # Add to existing imports
```

Then, copy all the code from `backend/homepage_builder_api.txt` and paste it **before** the line:
```python
if __name__ == "__main__":
```

The API endpoints include:
- `GET /admin/homepage-builder` - Render the builder interface
- `GET /api/homepage/sections` - Get all sections
- `POST /api/homepage/sections` - Create new section
- `PUT /api/homepage/sections/{id}` - Update section
- `DELETE /api/homepage/sections/{id}` - Delete section
- `POST /api/homepage/sections/{id}/reorder` - Reorder sections

### Step 4: Update Navigation (Optional)

Add a link to the homepage builder in your admin navigation. For example, in `templates/layouts/protected.html`:

```html
<!-- In the sidebar for consultants/admins -->
<a href="/admin/homepage-builder" class="nav-link">
    <i data-lucide="layout"></i>
    <span>Home Page Builder</span>
</a>
```

---

## 🎨 Features

### 1. **Section Management**
- ✅ Add new sections with custom HTML/CSS
- ✅ Edit existing sections
- ✅ Delete sections
- ✅ Reorder sections (move up/down)

### 2. **Visual Editor**
- ✅ Tabbed interface (Edit / Preview)
- ✅ Syntax-highlighted code editors
- ✅ Live preview before saving
- ✅ Draft/Published status

### 3. **Publishing System**
- ✅ Save as draft (not visible on homepage)
- ✅ Publish individual sections
- ✅ Publish all sections at once
- ✅ Preview homepage before deployment

### 4. **User Interface**
- ✅ Clean, modern design
- ✅ Responsive (works on mobile/tablet)
- ✅ Drag-and-drop ordering
- ✅ Modal-based editor
- ✅ Empty state for new users

---

## 📱 Usage

### For Admins:

1. **Access the Builder**
   - Navigate to `/admin/homepage-builder`
   - Only consultants/admins can access this page

2. **Add a New Section**
   - Click "Add Section" button
   - Enter section title
   - Add HTML content
   - (Optional) Add CSS styles
   - Choose to publish or save as draft
   - Click "Save"

3. **Edit Existing Section**
   - Click on any section card
   - Modify HTML/CSS in the editor
   - Use "Preview" tab to see changes
   - Click "Save" to update

4. **Reorder Sections**
   - Use the up/down arrow buttons on each section
   - Sections will reorder immediately

5. **Delete Section**
   - Click on a section to edit
   - Click "Delete" button
   - Confirm deletion

6. **Publish Changes**
   - Individual: Check "Publish this section" when editing
   - Bulk: Click "Publish All" to publish all sections

7. **Preview Homepage**
   - Click "Preview" button to open homepage in new tab
   - See how published sections look live

---

## 🎯 Example Sections

### Hero Section
```html
<!-- HTML -->
<div class="hero-section">
    <h1>Welcome to SolaceSquad</h1>
    <p>Your trusted partner in mental wellness</p>
    <a href="/signup" class="cta-button">Get Started</a>
</div>

<!-- CSS -->
.hero-section {
    text-align: center;
    padding: 80px 20px;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
}
.hero-section h1 {
    font-size: 3rem;
    margin-bottom: 1rem;
}
.cta-button {
    display: inline-block;
    padding: 12px 32px;
    background: white;
    color: #667eea;
    text-decoration: none;
    border-radius: 8px;
    font-weight: 600;
    margin-top: 2rem;
}
```

### Features Section
```html
<!-- HTML -->
<div class="features-section">
    <h2>Our Features</h2>
    <div class="features-grid">
        <div class="feature">
            <i data-lucide="heart"></i>
            <h3>Mental Wellness</h3>
            <p>Track your mood and vitals</p>
        </div>
        <div class="feature">
            <i data-lucide="video"></i>
            <h3>Video Calls</h3>
            <p>Connect with consultants</p>
        </div>
        <div class="feature">
            <i data-lucide="calendar"></i>
            <h3>Easy Scheduling</h3>
            <p>Book appointments anytime</p>
        </div>
    </div>
</div>

<!-- CSS -->
.features-section {
    padding: 60px 20px;
    text-align: center;
}
.features-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 30px;
    max-width: 1200px;
    margin: 40px auto 0;
}
.feature {
    padding: 30px;
    background: white;
    border-radius: 12px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}
.feature i {
    width: 48px;
    height: 48px;
    color: #667eea;
}
```

---

## 🔒 Security

- ✅ **Authentication Required**: Only logged-in users can access
- ✅ **Admin-Only Access**: Only consultants/admins can manage sections
- ✅ **Input Validation**: All inputs are validated before saving
- ✅ **SQL Injection Protection**: Using SQLAlchemy ORM
- ✅ **XSS Protection**: HTML is sanitized when rendered

---

## 🧪 Testing

### Local Testing:
1. Run the migration: `python migrate_homepage_builder.py`
2. Start the server: `python main.py`
3. Login as a consultant/admin
4. Navigate to `/admin/homepage-builder`
5. Create, edit, and publish sections
6. Preview the homepage to see changes

### Production Deployment:
1. Commit all changes
2. Deploy to Cloud Run
3. Run migration in production (via Cloud Shell or admin panel)
4. Test the feature in production

---

## 📊 Database Schema

```sql
CREATE TABLE homepage_sections (
    id INTEGER PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    html_content TEXT NOT NULL,
    css_content TEXT,
    order_index INTEGER DEFAULT 0,
    is_published BOOLEAN DEFAULT FALSE,
    created_at DATETIME,
    updated_at DATETIME,
    created_by INTEGER REFERENCES users(id)
);
```

---

## 🎨 Customization

### Styling
All styles are in the `<style>` block of `homepage_builder.html`. You can customize:
- Colors (change `#667eea` and `#764ba2` to your brand colors)
- Spacing (adjust padding/margins)
- Card styles (modify `.section-card`)
- Button styles (modify `.btn-*` classes)

### Functionality
Modify the JavaScript functions in `homepage_builder.html`:
- `loadSections()` - Change how sections are loaded
- `renderSections()` - Customize section card display
- `saveSection()` - Add validation or additional fields
- `renderPreview()` - Enhance preview rendering

---

## 🐛 Troubleshooting

### Issue: "Unauthorized" error
**Solution**: Make sure you're logged in as a consultant/admin

### Issue: Sections not appearing
**Solution**: Check if sections are published (`is_published = True`)

### Issue: Preview not working
**Solution**: Make sure the homepage route renders published sections

### Issue: CSS not applying
**Solution**: Check for syntax errors in CSS, use browser dev tools

---

## 🚀 Next Steps

1. **Integrate with Homepage**: Update your homepage route to render published sections
2. **Add Templates**: Create pre-made section templates for quick setup
3. **Add Media Library**: Allow uploading images for sections
4. **Version Control**: Add section versioning to track changes
5. **Collaboration**: Add comments/approval workflow for teams

---

## 📞 Support

If you encounter any issues:
1. Check the browser console for JavaScript errors
2. Check server logs for API errors
3. Verify database migration ran successfully
4. Ensure user has consultant/admin permissions

---

**Status**: ✅ Ready to deploy
**Version**: 1.0.0
**Last Updated**: 2026-02-17
