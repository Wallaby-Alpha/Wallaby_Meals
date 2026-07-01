import streamlit as st
import json
import os
import tempfile  # Added for bulletproof local file buffering
from itertools import combinations
import google.generativeai as genai
from PIL import Image
import pypdfium2 as pdfium

# 1. API Configuration (Securely pulling the token from Streamlit Secrets)
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.warning("Please configure your GEMINI_API_KEY in Streamlit Secrets to parse flyers.")

# 2. Optimization Engine Core
def optimize_weekly_menu(recipes, weekly_deals, last_week_ids):
    scored_weeks = []
    for combo in combinations(recipes, 4):
        base_score = 0
        cuisine_list = []
        observed_produce_tags = set()
        overlap_rewards = 0
        sale_match_rewards = 0
        
        for recipe in combo:
            r_id = recipe['recipe_id']
            cuisine_list.append(recipe['cuisine'])
            if r_id in last_week_ids:
                base_score -= 150  
                
            for ing in recipe['ingredients']:
                tag = ing['tag']
                if tag in weekly_deals:
                    sale_match_rewards += 15
                if ing['cat'] == 'produce':
                    if tag in observed_produce_tags:
                        overlap_rewards += 20
                    observed_produce_tags.add(tag)
                    
        unique_cuisines = len(set(cuisine_list))
        if unique_cuisines == 1:
            base_score -= 120
        elif unique_cuisines == 2:
            base_score -= 40
            
        final_score = base_score + overlap_rewards + sale_match_rewards
        scored_weeks.append((final_score, combo, cuisine_list))
        
    scored_weeks.sort(key=lambda x: x[0], reverse=True)
    return scored_weeks[0] if scored_weeks else (0, [], [])

# 3. AI Flyer Parsing Layer (Updated with stable TempFile stream)
def parse_flyer_with_ai(uploaded_file):
    """Uses Gemini Vision to read a flyer (Image or PDF) and extract master JSON keys."""
    try:
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        
        with open('normalized_meals.json', 'r') as f:
            recipes = json.load(f)
        valid_tags = set(ing['tag'] for r in recipes for ing in r['ingredients'])
        
        prompt = f"""
        Analyze this grocery store sales flyer. Extract any food items listed as on sale or as a price drop.
        Match the food items EXACTLY to this list of valid system tags. Do not invent tags outside of this list.
        Valid System Tags: {list(valid_tags)}
        
        Output your response ONLY as a clean JSON list of strings, like this:
        ["chicken_breast", "sweet_potatoes", "lime"]
        """
        
        contents = [prompt]
        
        if uploaded_file.name.lower().endswith('.pdf'):
            # Save bytes to a secure temp file to avoid stream manipulation bugs
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
                temp_pdf.write(uploaded_file.getbuffer())
                temp_pdf_path = temp_pdf.name
            
            # Open the temp file natively with pypdfium2
            pdf = pdfium.PdfDocument(temp_pdf_path)
            for page in pdf:
                bitmap = page.render(scale=2)
                contents.append(bitmap.to_pil())
            
            # Clean up the server file system afterward
            pdf.close()
            os.unlink(temp_pdf_path)
        else:
            image = Image.open(uploaded_file)
            contents.append(image)
        
        response = model.generate_content(contents)
        clean_json = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_json)
        
    except Exception as e:
        st.error(f"Error parsing flyer: {e}")
        return []

# 4. Streamlit UI View
st.set_page_config(page_title="Smart Meal Planner", layout="wide")
st.title("🛒 Multi-Store Smart Optimizer")
st.subheader("Upload flyer images or PDFs from different stores to find the best weekly plan.")

if os.path.exists('normalized_meals.json'):
    with open('normalized_meals.json', 'r') as f:
        recipes_database = json.load(f)
else:
    st.error("Missing normalized_meals.json file!")
    st.stop()

col1, col2 = st.columns([1, 2])

with col1:
    st.header("1. Settings & History")
    all_recipe_names = {r['name']: r['recipe_id'] for r in recipes_database}
    last_week = st.multiselect("Select meals you ate last week (to block repeats):", options=list(all_recipe_names.keys()))
    last_week_ids = [all_recipe_names[name] for name in last_week]
    
    st.header("2. Upload Circulars")
    # CRITICAL: Type definitions explicitly accept 'pdf'
    aldi_file = st.file_uploader("Upload ALDI Flyer (Image or PDF)", type=['png', 'jpg', 'jpeg', 'pdf'])
    safeway_file = st.file_uploader("Upload Safeway Flyer (Image or PDF)", type=['png', 'jpg', 'jpeg', 'pdf'])

with col2:
    st.header("3. Store Comparison")
    
    stores_to_process = {}
    if aldi_file:
        with st.spinner("AI is reading ALDI deals..."):
            stores_to_process["ALDI"] = parse_flyer_with_ai(aldi_file)
    if safeway_file:
        with st.spinner("AI is reading Safeway deals..."):
            stores_to_process["Safeway"] = parse_flyer_with_ai(safeway_file)
            
    if not stores_to_process:
        st.info("Upload at least one store flyer circular on the left to generate the optimal plan.")
    else:
        tabs = st.tabs(list(stores_to_process.keys()))
        
        for tab, (store_name, extracted_deals) in zip(tabs, stores_to_process.items()):
            with tab:
                st.write(f"**AI Extracted Sale Matches:** {', '.join(extracted_deals) if extracted_deals else 'None'}")
                
                score, menu, cuisines = optimize_weekly_menu(recipes_database, extracted_deals, last_week_ids)
                
                st.metric(label="Menu Optimization Score", value=score, delta=f"{len(extracted_deals)} active sales utilized")
                st.write(f"**Cuisine Profiles:** {', '.join([c.upper() for c in cuisines])}")
                
                st.markdown("### 📋 Recommended Menu")
                for idx, meal in enumerate(menu, 1):
                    st.write(f"**{idx}. {meal['name']}** ({meal['cuisine'].title()})")
                    
                fresh, produce, staples = set(), set(), set()
                for meal in menu:
                    for ing in meal['ingredients']:
                        if ing['cat'] == 'fresh': fresh.add(ing['tag'])
                        elif ing['cat'] == 'produce': produce.add(ing['tag'])
                        else: staples.add(ing['tag'])
                        
                sc1, sc2, sc3 = st.columns(3)
                with sc1:
                    st.markdown("🍏 **Fresh Produce Bridges**")
                    for p in produce: st.checkbox(p, key=f"{store_name}_prod_{p}")
                with sc2:
                    st.markdown("🥩 **Fresh Proteins (Buy on Sale)**")
                    for f in fresh: st.checkbox(f, key=f"{store_name}_fresh_{f}")
                with sc3:
                    st.markdown("🧂 **Pantry Staples (Verify)**")
                    for s in staples: st.checkbox(s, key=f"{store_name}_staple_{s}")
