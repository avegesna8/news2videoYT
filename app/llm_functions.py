import os
from openai import OpenAI
from dotenv import load_dotenv
from models import TopHeadlinesResponse, ComedicScriptResponse

load_dotenv()
client = OpenAI(
    base_url="https://router.huggingface.co/v1",
    api_key=os.getenv("HF_TOKEN"),
)

#Select Top 3 Headlines
def select_top_three_headlines(news_items):
    if not news_items:
        return []
    
    headlines_text = "\n".join([f"{i+1}. {item['title']}" for i, item in enumerate(news_items)])

    prompt = f"""
        You are a sports news editor. Below are {len(news_items)} NFL/ESPN headlines. 
        Select the TOP 3 most important, newsworthy, and impactful headlines that would be most interesting to NFL fans.

        Headlines:
        {headlines_text}

        Return the indices (1-based) of your top 3 choices in order of importance.
    """

    try:
        completion = client.chat.completions.create(
            model="meta-llama/Llama-3.1-8B-Instruct:fireworks-ai",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "top_headlines_response",
                    "schema": TopHeadlinesResponse.model_json_schema(),
                    "strict": True
                }
            },
            max_tokens=100,
            temperature=0.3
        )

        response_content = completion.choices[0].message.content
        response_data = TopHeadlinesResponse.model_validate_json(response_content)

        #Convert 1-based indices to 0-based and get Selected Headlines
        selected_indices = [idx - 1 for idx in response_data.selected_indices]  # Convert to 0-based
        selected_headlines = [news_items[i] for i in selected_indices if 0 <= i < len(news_items)]
        
        return selected_headlines
            
    except Exception as e:
        print(f"Error with LLM selection: {e}")
        return news_items[:3]  # Fallback to first 3

#Generate Comedic Script from Article Data
def generate_comedic_script(article_data, max_paragraphs=20, max_chars_per_paragraph=500):
    if not article_data or not article_data.get('paragraphs'):
        return {"script": "No article content available", "is_too_long": False}
    
    # Check if article is too long
    total_paragraphs = len(article_data['paragraphs'])
    if total_paragraphs > max_paragraphs:
        return {"script": "", "is_too_long": True}
    
    # Chunk and truncate paragraphs
    processed_paragraphs = []
    for para in article_data['paragraphs'][:max_paragraphs]:
        if len(para) > max_chars_per_paragraph:
            # Truncate and add ellipsis
            truncated = para[:max_chars_per_paragraph].rsplit(' ', 1)[0] + "..."
            processed_paragraphs.append(truncated)
        else:
            processed_paragraphs.append(para)
    
    # Prepare article content for prompt
    article_content = "\n\n".join(processed_paragraphs)
    
    prompt = f"""
    You are a comedic news anchor writing a script to deliver NFL news in an entertaining way.
    
    Article Information:
    Title: {article_data.get('title', 'N/A')}
    Author: {article_data.get('author', 'N/A')}
    Published: {article_data.get('published', 'N/A')}
    
    Article Content:
    {article_content}
    
    Create a comedic news script that:
    1. Is engaging and entertaining for NFL fans
    2. Includes humor and personality
    3. Delivers the key information from the article
    4. Is appropriate for a news character to read aloud
    5. Is between 100-120 words
    6. Includes some comedic commentary or reactions
    
    Write as if you're a charismatic sports news anchor with personality.
    """

    try:
        completion = client.chat.completions.create(
            model="meta-llama/Llama-3.1-8B-Instruct:fireworks-ai",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "comedic_script_response",
                    "schema": ComedicScriptResponse.model_json_schema(),
                    "strict": True
                }
            },
            max_tokens=500,
            temperature=0.7
        )
        
        response_content = completion.choices[0].message.content
        response_data = ComedicScriptResponse.model_validate_json(response_content)
        
        return {
            "script": response_data.script,
            "is_too_long": response_data.is_too_long
        }
            
    except Exception as e:
        print(f"Error generating comedic script: {e}")
        return {
            "script": f"Breaking news: {article_data.get('title', 'NFL Update')} - Error Processing Article",
            "is_too_long": False
        }

#CLI Test
if __name__ == "__main__":
    from get_news_links import get_nfl_links
    from espn_scraper import get_link, parse_espn_article_html
    
    # Get news items (title + url)
    news_items = get_nfl_links()
    print(f"Found {len(news_items)} news items")
    
    # Select top 3 headlines
    top_headlines = select_top_three_headlines(news_items)
    
    print("\nTop 3 Headlines:")
    for i, item in enumerate(top_headlines, 1):
        print(f"{i}. {item['title']}")
        print(f"   URL: {item['url']}")
        
        # Generate comedic script for first headline as example
        if i == 1:
            print(f"\nGenerating comedic script...")
            try:
                response = get_link(item['url'])
                article_data = parse_espn_article_html(response.text, response.url)
                script_result = generate_comedic_script(article_data)
                
                if script_result['is_too_long']:
                    print("Article is too long for script generation")
                else:
                    print(f"Script Preview: {script_result['script'][:200]}...")
            except Exception as e:
                print(f" Error generating script: {e}")
        print()
