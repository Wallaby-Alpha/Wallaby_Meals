import streamlit as st
import json
import os
from itertools import combinations

# --- SYSTEM STYLING & CONFIGURATION ---
st.set_page_config(page_title="Zero-Decision Dinner Planner", layout="wide")

# Secure but simple admin passcode to access backend updates
ADMIN_PASSWORD = "admin" 

# --- DATA LOADING & NORMALIZATION LAYER ---
def load_recipes():
    if os.path.exists('normalized_meals.json'):
        with open('normalized_meals.json', 'r') as f:
            recipes = json.load(f)
            
        # Clean up tags and classifications dynamically to enforce database rules
        for r in recipes:
            # 1. Fix Cuisine Classification Tags
            name_lower = r['name'].lower()
            if any(k in name_lower for k in ['stir-fry', 'stir_fry', 'satay', 'teriyaki', 'thai', 'asian', 'szechuan', 'curry']):
                r['cuisine'] = 'asian'
            elif any(k in name_lower for k in ['burrito', 'taco', 'enchilada', 'fajita', 'mexi', 'quesadilla', 'poblano']):
                r['cuisine'] = 'mexican'
            elif any(k in name_lower for k in ['balsamic', 'tuscan', 'caprese', 'mediterranean', 'greek', 'fig_chicken']):
                r['cuisine'] = 'mediterranean'
            elif any(k in name_lower for k in ['burger', 'frites', 'steakhouse', 'bbq', 'crispy chicken', 'flautas']):
                r['cuisine'] = 'american'

            # 2. Enforce Ingredient Tag Merges
            for ing in r['ingredients']:
                tag = ing['tag']
                
                # Consolidate all chicken breast variants & cutlets
                if tag in ['chicken_cutlets', 'chicken_breast_strips', 'boneless_chicken_breast_pieces', 'chopped_chicken_breast']:
                    ing['tag'] = 'chicken_breast'
                    
                # Fix ground pork spelling typo
                elif tag == 'grounf_pork':
                    ing['tag'] = 'ground_pork'
                    
                # Merge all steak cuts into a single tag
                elif tag in ['beef_tenderloin_steak', 'beef_tenderloin_text', 'beef_tenderloin_steaks', 'diced_steak', 'sirloin_steak']:
                    ing['tag'] = 'steak'
                    
                # Reclassify stock foundations & broths out of proteins into staples
                elif 'stock' in tag or 'broth' in tag or 'demi_glace' in tag or 'glaze' in tag:
                    ing['cat'] = 'staple'
                    if 'chicken' in tag: 
                        ing['tag'] = 'chicken_stock'
                    elif 'beef' in tag: 
                        ing['tag'] = 'beef_stock'
                        
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

# Instantiate Databases
recipes_database = load_recipes()
active_store_deals = load_deals()

# Re-compile clean arrays for the Admin panel checkboxes
all_system_tags = sorted(list(set(ing['tag'] for r in recipes_database for ing in r['ingredients'])))
proteins_list = sorted(list(set(ing['tag'] for r in recipes_database for ing in r['ingredients'] if ing['cat'] == 'fresh')))
produce_list = sorted(list(set(ing['tag'] for r in recipes_database for ing in r['ingredients'] if ing['cat'] == 'produce')))
other_list = sorted([tag for tag in all_system_tags if tag not in proteins_list and tag not in produce_list])

# --- SALE-FIRST OPTIMIZATION CORE ---
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
                
                # High-weight sales matching structure
                if tag in weekly_deals:
                    if ing['cat'] == 'fresh':
                        sale_match_rewards += 60  # Massive priority multiplier for sale proteins!
                    else:
                        sale_match_rewards += 25  # Solid reward for sale produce/staples
                        
                if ing['cat'] == 'produce':
                    if tag in observed_produce_tags:
                        overlap_rewards += 15  # Encourages vegetable cross-utilization
                    observed_produce_tags.add(tag)
                    
        # Variety Constraints
        unique_cuisines = len(set(cuisine_list))
        if unique_cuisines == 1:
            base_score -= 150  # Strict penalty for zero variety
        elif unique_cuisines == 2:
            base_score -= 50   # Moderate penalty for low variety
            
        final_score = base_score + overlap_rewards + sale_match_rewards
        scored_weeks.append((final_score, combo, cuisine_list))
        
    scored_weeks.sort(key=lambda x: x[0], reverse=True)
    return scored_weeks[0] if scored_weeks else (0, [], [])

# --- USER-FACING FRONTEND VIEW ---
st.title("🍽️ Clean Slate Dinner Planner")
st.write("We match local circulars against minimized food-waste arrays. Pick your store, grab your menu, and cook.")

# Store Dropdown Selector
store_mapping = {
    "Harris Teeter": "harris_teeter",
    "Safeway": "safeway",
    "Lidl": "lidl",
    "Giant": "giant"
}

selected_tab = st.selectbox("Where are you shopping this week?", options=list(store_mapping.keys()))
db_store_key = store_mapping[selected_tab]

# Generate Optimization Run
current_deals = active_store_deals.get(db_store_key, [])
best_score, menu, cuisines = optimize_weekly_menu(recipes_database, current_deals)

if not menu:
    st.info("No plans generated. Please verify internal database state.")
else:
    col_menu, col_list = st.columns([4, 3])
    
    with col_menu:
        st.markdown(f"### 📋 Your 4-Meal Plan for {selected_tab}")
        st.caption(f"Cuisine balance metrics: {', '.join([c.upper() for c in cuisines])}")
        
        for idx, meal in enumerate(menu, 1):
            with st.container(border=True):
                st.markdown(f"#### {idx}. {meal['name']}")
                st.markdown(f"**Style Category:** {meal['cuisine'].title()}")
                
    with col_list:
        st.markdown("### 🛒 Consolidated Shopping List")
        fresh, produce, staples = set(), set(), set()
        for meal in menu:
            for ing in meal['ingredients']:
                if ing['cat'] == 'fresh': fresh.add(ing['tag'])
                elif ing['cat'] == 'produce': produce.add(ing['tag'])
                else: staples.add(ing['tag'])
                
        st.markdown("**🥩 Proteins (Prioritized Sales)**")
        for f in fresh:
            is_on_sale = "🔥 (On Sale!)" if f in current_deals else ""
            st.checkbox(f"{f.replace('_', ' ').title()} {is_on_sale}", key=f"user_f_{f}")
            
        st.markdown("**🍏 Fresh Produce & Overlaps**")
        for p in produce:
            is_on_sale = "🔥 (On Sale!)" if p in current_deals else ""
            st.checkbox(f"{p.replace('_', ' ').title()} {is_on_sale}", key=f"user_p_{p}")
            
        st.markdown("**🧂 Pantry Staples (Verify Cabinet)**")
        for s in staples:
            st.checkbox(s.replace('_', ' ').title(), key=f"user_s_{s}")

# --- INTERNAL ADMIN DATABASE PORTAL ---
st.markdown("---")
with st.expander("🔐 Open Internal Admin Portal"):
    password_input = st.text_input("Enter Admin Password to modify weekly sales:", type="password")
    
    if password_input == ADMIN_PASSWORD:
        st.success("Access Granted. Update weekly circular vectors below.")
        
        admin_store_select = st.selectbox("Select Store Circular to Edit:", options=list(store_mapping.keys()))
        admin_store_key = store_mapping[admin_store_select]
        
        existing_deals = active_store_deals.get(admin_store_key, [])
        new_deals_list = []
        
        st.markdown(f"#### Select Active Circular Discounts for {admin_store_select}")
        
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
                
        if st.button(f"Save and Push {admin_store_select} Deals Live"):
            active_store_deals[admin_store_key] = new_deals_list
            save_deals(active_store_deals)
            st.success(f"Successfully processed updates for {admin_store_select}! Frontend layers refreshed.")
            st.rerun()
