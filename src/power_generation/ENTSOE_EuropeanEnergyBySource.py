import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from entsoe import EntsoePandasClient
from datetime import timedelta
import logging
from pathlib import Path
import sys
from typing import Dict, List, Optional, Tuple

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class EnergyDataAnalyzer:
    """
    Analyzes energy generation data from multiple European countries.
    Handles data availability issues and creates standardized visualizations.
    """
    
    def __init__(self, api_key: str):
        """Initialize with ENTSO-E API key."""
        self.client = EntsoePandasClient(api_key=api_key)
        self.countries = {
            'FR': 'France',
            'DE_LU': 'Germany/Luxembourg',
            'IT': 'Italy',
            'ES': 'Spain'
        }
        
        # Define standard colors for each generation type
        self.color_map = {
            'Nuclear': '#7E57C2',         # Purple
            'Fossil Gas': '#FF7043',      # Orange-Red
            'Coal and Lignite': '#5D4037', # Brown
            'Wind': '#81C784',            # Light Green
            'Solar': '#FFD54F',           # Yellow
            'Hydro': '#4FC3F7',          # Light Blue
            'Other Renewables': '#66BB6A', # Green
            'Fossil Oil': '#8D6E63',      # Dark Brown
            'Other': '#90A4AE',           # Grey
            'Biomass': '#A5D6A7',         # Pale Green
            'Waste': '#FFAB91'            # Pale Orange
        }
        
        # Standard aggregation mapping
        self.agg_map = {
            "Wind": [
                "Wind Offshore",
                "Wind Onshore",
            ],
            "Other Renewables": [
                "Other renewable",
                "Waste",
                "Geothermal",
                "Biomass"
            ],
            "Hydro": [
                "Hydro Run-of-river and poundage",
                "Hydro Water Reservoir",
                "Hydro Pumped Storage"
            ],
            "Coal and Lignite": [
                "Fossil Brown coal/Lignite",
                "Fossil Coal-derived gas",
                "Fossil Hard coal"
            ]
        }

    def find_latest_data_date(self, country_code: str) -> Optional[pd.Timestamp]:
        """
        Find the most recent date with available data for a country.
        Returns None if no data is found within the search period.
        """
        end = pd.Timestamp.now(tz='Europe/Brussels')
        start = end - timedelta(days=30)  # Look back 30 days
        
        try:
            df = self.client.query_generation(
                country_code=country_code,
                start=start,
                end=end
            )
            if not df.empty:
                return df.index[-1]
            return None
        except Exception as e:
            logger.warning(f"Error finding latest data for {country_code}: {e}")
            return None

    def aggregate_sources(self, df_gen: pd.DataFrame) -> pd.DataFrame:
        """Aggregate generation sources according to predefined mapping."""
        df_agg = pd.DataFrame(index=df_gen.index)
        
        for col in df_gen.columns:
            found_group = None
            for group_name, source_list in self.agg_map.items():
                if col in source_list:
                    found_group = group_name
                    break

            if found_group:
                if found_group not in df_agg.columns:
                    df_agg[found_group] = 0.0
                df_agg[found_group] += df_gen[col]
            else:
                if col not in df_agg.columns:
                    df_agg[col] = df_gen[col]
                else:
                    df_agg[col] += df_gen[col]
        
        return df_agg

    def create_generation_plot(
        self, 
        df_agg: pd.DataFrame, 
        country_name: str,
        output_path: Path,
        stats: Dict
    ) -> bool:
        """
        Create and save a stacked area plot for generation data.
        Returns True if successful, False otherwise.
        """
        """Create and save a stacked area plot for generation data."""
        num_cols = len(df_agg.columns)
        palette = sns.color_palette("tab20", n_colors=num_cols)

        plt.figure(figsize=(15, 8))
        ax = plt.gca()

        df_agg.plot.area(
            ax=ax,
            title=f"{country_name} Power Generation Mix\n{df_agg.index[0].strftime('%Y-%m-%d')} to {df_agg.index[-1].strftime('%Y-%m-%d')}",
            color=palette
        )
        
        ax.set_xlabel("Time")
        ax.set_ylabel("Power [MW]")

        # Add day boundary lines
        for day in pd.date_range(df_agg.index[0], df_agg.index[-1], freq='D'):
            ax.axvline(day, color='gray', linestyle='--', linewidth=0.5, alpha=0.5)

        plt.legend(loc='center left', bbox_to_anchor=(1.05, 0.5))
        plt.tight_layout()
        
        # Save the plot
        try:
            # Ensure the output directory exists
            output_path.mkdir(parents=True, exist_ok=True)
            
            # Create the filename
            filename = f"{country_name.lower().replace('/', '_')}_generation.png"
            filepath = output_path / filename
            
            # Save the plot
            plt.savefig(filepath, bbox_inches='tight', dpi=300)
            plt.close()
            
            # Verify the file was created
            if filepath.exists():
                logger.info(f"Successfully saved plot to {filepath}")
                return True
            else:
                logger.error(f"Failed to save plot to {filepath}")
                return False
                
        except Exception as e:
            logger.error(f"Error saving plot for {country_name}: {e}")
            plt.close()
            return False

    def calculate_statistics(self, df_agg: pd.DataFrame) -> Dict:
        """Calculate key statistics from the generation data."""
        # Calculate total generation
        total_generation = df_agg.sum(axis=1)
        
        # Convert to daily data for some metrics
        daily_generation = total_generation.resample('D').mean()
        
        stats = {
            'max_power_mw': total_generation.max(),
            'min_power_mw': total_generation.min(),
            'avg_power_mw': total_generation.mean(),
            'daily_volatility': daily_generation.std() / daily_generation.mean() * 100,  # CV as percentage
            'peak_hour': total_generation.idxmax().strftime('%Y-%m-%d %H:%M'),
            'trough_hour': total_generation.idxmin().strftime('%Y-%m-%d %H:%M')
        }
        
        return stats

    def check_data_quality(self, df_agg: pd.DataFrame) -> List[str]:
        """Check for potential data quality issues."""
        issues = []
        
        # Check for unusually low total generation
        total_generation = df_agg.sum(axis=1)
        mean_generation = total_generation.mean()
        low_threshold = mean_generation * 0.2  # 20% of mean
        
        low_periods = total_generation[total_generation < low_threshold]
        if not low_periods.empty:
            issues.append(f"Found unusually low generation periods: {low_periods.index.strftime('%Y-%m-%d %H:%M').tolist()}")
        
        # Check for missing major sources
        major_sources = ['Fossil Gas', 'Nuclear', 'Coal and Lignite']
        for source in major_sources:
            if source in df_agg.columns:
                zero_periods = df_agg[df_agg[source] == 0][source]
                if not zero_periods.empty:
                    issues.append(f"Found periods with zero {source} generation: {zero_periods.index.strftime('%Y-%m-%d %H:%M').tolist()}")
        
        return issues

    def analyze_country(
        self, 
        country_code: str,
        output_path: Path
    ) -> Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame], Optional[Dict]]:
        """Analyze generation data for a specific country."""
        latest_date = self.find_latest_data_date(country_code)
        if not latest_date:
            logger.error(f"No recent data found for {country_code}")
            return None, None

        start = latest_date - timedelta(days=10)
        end = latest_date + timedelta(hours=1)

        try:
            df_raw = self.client.query_generation(
                country_code=country_code,
                start=start,
                end=end
            )
            
            if df_raw.empty:
                logger.error(f"No data returned for {country_code}")
                return None, None

            df_gen = df_raw.xs("Actual Aggregated", axis=1, level=1)
            df_agg = self.aggregate_sources(df_gen)
            
            # Calculate generation shares
            total_gen = df_agg.sum(axis=1)
            df_share = df_agg.div(total_gen, axis=0).fillna(0)
            
            # Calculate statistics
            stats = self.calculate_statistics(df_agg)
            
            # Check data quality
            quality_issues = self.check_data_quality(df_agg)
            if quality_issues:
                logger.warning(f"Data quality issues for {country_code}:")
                for issue in quality_issues:
                    logger.warning(f"  - {issue}")
            
            return df_agg, df_share, stats

        except Exception as e:
            logger.error(f"Error analyzing {country_code}: {e}")
            return None, None, None

def main():
    """Main execution function."""
    try:
        # Create output directory with absolute path
        output_path = Path(__file__).parent.parent / "images"
        
        # Ensure the directory exists
        output_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Output directory created/verified at: {output_path}")
    except Exception as e:
        logger.error(f"Failed to create output directory: {e}")
        sys.exit(1)  # Exit if we can't create the output directory

    # Initialize analyzer
    API_KEY = "yourentsoeapi"  # Replace with your API key
    analyzer = EnergyDataAnalyzer(API_KEY)

    # Process each country
    results = {}
    for country_code, country_name in analyzer.countries.items():
        logger.info(f"Processing {country_name}...")
        
        df_agg, df_share, stats = analyzer.analyze_country(country_code, output_path)
        
        if df_agg is not None and df_share is not None and stats is not None:
            analyzer.create_generation_plot(df_agg, country_name, output_path, stats)
            results[country_code] = {
                'generation_mix': df_share.mean().round(3),
                'statistics': stats
            }
            
            logger.info(f"Average generation mix for {country_name}:")
            print(f"\n{country_name} Generation Mix:")
            print((df_share.mean() * 100).sort_values(ascending=False).round(2).astype(str) + " %")
        else:
            logger.warning(f"Skipping visualization for {country_name} due to data issues")

if __name__ == "__main__":
    main()





