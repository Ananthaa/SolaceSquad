with open(r'c:\Anantha\Projects\Soul Squad\backend\main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find and replace the function signature
old_signature = 'async def list_consultants(request: Request, db: Session = Depends(get_db)):'
new_signature = 'async def list_consultants(request: Request, free: str = None, db: Session = Depends(get_db)):'

content = content.replace(old_signature, new_signature)

# Find the query and add the filter
old_query = '''    consultant_profiles = db.query(ConsultantProfile, User).join(
        User, ConsultantProfile.user_id == User.id
    ).filter(
        User.user_type == "consultant",
        User.is_active == True,
        ConsultantProfile.is_approved == True
    ).all()'''

new_query = '''    query = db.query(ConsultantProfile, User).join(
        User, ConsultantProfile.user_id == User.id
    ).filter(
        User.user_type == "consultant",
        User.is_active == True,
        ConsultantProfile.is_approved == True
    )
    
    # Filter for free consultants if requested
    if free == "true":
        query = query.filter(ConsultantProfile.consultation_fee == 0)
    
    consultant_profiles = query.all()'''

content = content.replace(old_query, new_query)

with open(r'c:\Anantha\Projects\Soul Squad\backend\main.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Successfully modified list_consultants function to support free consultant filtering')
