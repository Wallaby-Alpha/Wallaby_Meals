import streamlit as st
import json
import os
from itertools import combinations

# --- STYLING & CONFIGURATION ---
st.set_page_config(page_title="Zero-Decision Dinner Planner", layout="wide")

# Secure but simple admin passcode
ADMIN_PASSWORD = "admin" 

# --- ENHANCED DATA LOADING & NORMALIZATION CLEANUP ---
def load_recipes():
    if os.path.exists('normalized_meals.json'):
        with open('normalized_meals.json', 'r') as f:
            recipes = json.load(f)
            
        # Clean up tags dynamically to enforce your rules
        for r in recipes:
            for ing in r['ingredients']:
                tag = ing['tag']
                
                # Rule 1: Combine chicken cutlets into chicken breast
                if tag == 'chicken_cutlets':
                    ing['tag'] = 'chicken_breast'
                    
                # Rule 2: Fix the grounf pork typo
                if tag == 'grounf_pork':
                    ing['tag'] = 'ground_pork'
                    
                # Rule 3: Merge chicken broth/water & stock, force to staple category
                if tag in ['chicken_broth_or_water', 'chicken_stock_concentrate']:
                    ing['tag'] = 'chicken_stock'
                    ing['cat'] = 'staple'
                    
                # Bonus Cleanup: Fix beef stock categorizations to staples as well
                if 'stock' in tag or 'broth' in tag:
                    ing['cat'] = 'staple'
                    
        return recipes
    return []

def load_deals():
    if os.path.exists('active_deals.json'):
        with open('active_deals.json', 'r') as f:
            return json.load(f)
    return {"harris_teeter": [], "safeway": [], "lidl": [], "giant": []}

def save_deals(deals_dict):
    with open('active_deals.json', 'w') as f:
        json.dump(deals_dict, f, indent=2)

recipes_database = load_recipes()
active_store_deals = load_deals()

# Re-compile clean, distinct system tags for the Admin panel checklist
all_system_tags = sorted(list(set(ing['tag'] for r in recipes_database for ing in r['ingredients'])))
proteins_list = sorted(list(set(ing['tag'] for r in recipes_database for ing in r['ingredients'] if ing['cat'] == 'fresh')))
produce_list = sorted(list(set(ing['tag'] for r in recipes_database for ing in r['ingredients'] if ing['cat'] == 'produce')))
other_list = sorted([tag for tag in all_system_tags if tag not in proteins_list and tag not in produce_list])

# --- ALGORITHMIC OPTIMIZER CORE ---
def optimize_weekly_menu(recipes, weekly_deals):
    scored_weeks = []
    for combo in combinations(recipes, 4):
        base_score = 0
        cuisine_list = []
        observed_produce_tags = set()
        overlap_rewards = 0
        sale_match_rewards = 0
        
        for recipe in combo:
            cuisine_list.append(recipe['cuisine'])
            for ing in recipe['ingredients']:
                tag = ing['tag']
                if tag in weekly_deals:
                    sale_match_rewards += 15  # Reward sale items
                if ing['cat'] == 'produce':
                    if tag in observed_produce_tags:
                        overlap_rewards += 20  # Reward cross-utilization
                    observed_produce_tags.add(tag)
                    
        unique_cuisines = len(set(cuisine_list))
        if unique_cuisines == 1:
            base_score -= 120  # Penalty for zero variety
        elif unique_cuisines == 2:
            base_score -= 40
            
        final_score = base_score + overlap_rewards + sale_match_rewards
        scored_weeks.append((final_score, combo, cuisine_list))
        
    scored_weeks.sort(key=lambda x: x[0], reverse=True)
    return scored_weeks[0] if scored_weeks else (0, [], [])

# --- USER INTERFACE VIEW ---
st.title("🍽️ Clean Slate Dinner Planner")
st.write("We scan local sales and map ingredient waste profiles. Pick a store, grab your grocery list, and cook.")

# Store Selector Tabs
store_mapping = {
    "Harris Teeter": "harris_teeter",
    "Safeway": "safeway",
    "Lidl": "lidl",
    "Giant": "giant"
}

selected_tab = st.selectbox("Where are you shopping this week?", options=list(store_mapping.keys()))
db_store_key = store_mapping[selected_tab]

# Fetch deals and compile menu
current_deals = active_store_deals.get(db_store_key, [])
best_score, menu, cuisines = optimize_weekly_menu(recipes_database, current_deals)

if not menu:
    st.info("No meals generated. Please check database data inputs.")
else:
    # Render Output Layout
    col_menu, col_list = st.columns([4, 3])
    
    with col_menu:
        st.markdown(f"### 📋 Your 4-Meal Plan for {selected_tab}")
        st.caption(f"Optimized cuisine profile: {', '.join([c.upper() for c in cuisines])}")
        
        for idx, meal in enumerate(menu, 1):
            with st.container(border=True):
                st.markdown(f"#### {idx}. {meal['name']}")
                st.markdown(f"**Style:** {meal['cuisine'].title()}")
                
    with col_list:
        st.markdown("### 🛒 Consolidated Shopping List")
        fresh, produce, staples = set(), set(), set()
        for meal in menu:
            for ing in meal['ingredients']:
                if ing['cat'] == 'fresh': fresh.add(ing['tag'])
                elif ing['cat'] == 'produce': produce.add(ing['tag'])
                else: staples.add(ing['tag'])
                
        st.markdown("**🥩 Proteins (Buy on Sale)**")
        for f in fresh:
            is_on_sale = "🔥 (On Sale!)" if f in current_deals else ""
            st.checkbox(f"{f.replace('_', ' ').title()} {is_on_sale}", key=f"user_f_{f}")
            
        st.markdown("**🍏 Fresh Produce & Bridges**")
        for p in produce:
            is_on_sale = "🔥 (On Sale!)" if p in current_deals else ""
            st.checkbox(f"{p.replace('_', ' ').title()} {is_on_sale}", key=f"user_p_{p}")
            
        st.markdown("**🧂 Pantry Items (Verify)**")
        for s in staples:
            st.checkbox(s.replace('_', ' ').title(), key=f"user_s_{s}")

# --- INTERNAL ADMIN DASHBOARD VIEW ---
st.markdown("---")
with st.expander("🔐 Open Internal Admin Portal"):
    password_input = st.text_input("Enter Admin Password to modify weekly sales:", type="password")
    
    if password_input == ADMIN_PASSWORD:
        st.success("Access Granted. Update weekly sale sheets below.")
        
        admin_store_select = st.selectbox("Select Store Circular to Edit:", options=list(store_mapping.keys()))
        admin_store_key = store_mapping[admin_store_select]
        
        # Pull existing saved deals for default checkboxes
        existing_deals = active_store_deals.get(admin_store_key, [])
        new_deals_list = []
        
        st.markdown(f"#### Edit Active Sales for {admin_store_select}")
        
        # Render Admin input checkboxes inside 3 clean columns
        ac1, ac2, ac3 = st.columns(3)
        
        with ac1:
            st.markdown("**🥩 Target Proteins**")
            for protein in proteins_list:
                chk = st.checkbox(protein.replace('_', ' ').title(), value=(protein in existing_deals), key=f"adm_prot_{protein}")
                if chk: new_deals_list.append(protein)
                
        with ac2:
            st.markdown("**🥦 Target Produce**")
            for prod in produce_list:
                chk = st.checkbox(prod.replace('_', ' ').title(), value=(prod in existing_deals), key=f"adm_prod_{prod}")
                if chk: new_deals_list.append(prod)
                
        with ac3:
            st.markdown("**🥫 Other/Staples**")
            for other in other_list:
                chk = st.checkbox(other.replace('_', ' ').title(), value=(other in existing_deals), key=f"adm_oth_{other}")
                if chk: new_deals_list.append(other)
                
        # Save Trigger Button
        if st.button(f"Save and Push {admin_store_select} Deals Live"):
            active_store_deals[admin_store_key] = new_deals_list
            save_deals(active_store_deals)
            st.success(f"Successfully saved changes for {admin_store_select}! The public site has updated.")
            st.rerun()
