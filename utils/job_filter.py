from typing_extensions import Dict,Optional
import re

class JobFilter:
    WORDS_TO_AVOID = {"wordpress", "shopify", "woocommerce", "magento", "wix", "squarespace", "webflow", "video editing", "laravel"}
    MINIMUM_SPENT = 50000  # Minimum amount spent in dollars
    DURATION_TYPES = {"duration1", "duration2", "duration3", "duration4"}  # Example duration types
    
    def __init__(self, words_to_avoid: Optional[set[str]] = {}):
        self.words_to_avoid = {word_to_avoid.lower() for word_to_avoid in words_to_avoid } | self.WORDS_TO_AVOID

    def avoid_keywords(self,description: str) -> bool:
        try:
            description = description.lower()
            for word in self.words_to_avoid:
                if word in description:
                    return True
            return False
        except Exception as e:
            print(f"Error in avoid_keywords: {e}")
            return False
    
    def check_min_spent(self,total_spent: str) -> bool:
        try:
            return float(total_spent) >= self.MINIMUM_SPENT
        except ValueError:
            return False
        
    def check_duration(self,duration_type: str, total_spent:float) -> bool:
        try:
            if not duration_type == "duration1":
                return True
            elif duration_type == "duration1" and total_spent >= 200:
                return True
            else:
                return False
        except Exception as e:
            print(f"Error in check_duration: {e}")
            return False
        
        
    def get_total_spent(self, total_spent: str) -> str:
        try:
            if total_spent == "N/A":
                return None
            s = str(total_spent).replace(',', '').strip()
            m = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*([kKmM]?)', s)
            if not m:
                return None
            try:
                num = float(m.group(1))
                suffix = m.group(2).lower()
                # Apply multiplier
                if suffix == 'k':
                    num *= 1_000
                elif suffix == 'm':
                    num *= 1_000_000
                return num
            except ValueError:
                return None
        except Exception as e:
            print(f"Error in get_total_spent: {e}")
            return None
    
    def is_job_allowed(self, job_details: Dict) -> bool:
        """Check if the job is allowed based on the title and description."""
        try:
            job_description = job_details.get("summary", "").lower()
            total_spent_str = job_details.get("total_spent", "N/A")
            total_spent = self.get_total_spent(total_spent_str)
            duration_type = job_details.get("duration_type", "N/A")
            qualified = job_details.get("qualified", True)
            payment_type = job_details.get("job_type", "N/A")
            payment_verified = job_details.get("payment_verified", False)
            hire_rate = float(re.search(r'(\d+)%',job_details.get("hire_rate", "")).group(1))
            
            if not payment_verified:
                return False
            
            if not qualified:
                return False
            if total_spent is None:
                return False
            if self.avoid_keywords(job_description):
                return False
            if not self.check_min_spent(total_spent):
                return False
            if not self.check_duration(duration_type, total_spent):
                return False
            if payment_type == "Fixed Price":
                try:
                    if float(job_details.get("hourly_rate", "").replace("$", "")) <= 3.5:
                        return False
                except ValueError:
                    return False
            if hire_rate < 50 and total_spent < 200:
                return False
            return True
        except Exception as e:
            print(f"Error in is_job_allowed: {e}")
            return False