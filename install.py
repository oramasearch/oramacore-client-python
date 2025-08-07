#!/usr/bin/env python3
"""
Installation helper script for Orama Python client.

Usage:
    python install.py --help
    python install.py basic
    python install.py dev  
    python install.py prod
    python install.py optional
"""

import sys
import subprocess
import argparse
from pathlib import Path

def run_pip_install(requirements_file: str):
    """Run pip install with the specified requirements file."""
    if not Path(requirements_file).exists():
        print(f"❌ Requirements file not found: {requirements_file}")
        sys.exit(1)
    
    print(f"📦 Installing dependencies from {requirements_file}...")
    try:
        result = subprocess.run([
            sys.executable, "-m", "pip", "install", "-r", requirements_file
        ], check=True, capture_output=True, text=True)
        print(f"✅ Successfully installed dependencies from {requirements_file}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e.stderr}")
        return False

def install_package_editable():
    """Install the package in editable mode."""
    print("📦 Installing oramacore-client in editable mode...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "-e", "."], check=True)
        print("✅ Successfully installed oramacore-client in editable mode")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install package in editable mode: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(
        description="Install Orama Python client with different dependency sets"
    )
    parser.add_argument(
        "mode",
        choices=["basic", "dev", "prod", "optional", "all"],
        help="Installation mode"
    )
    parser.add_argument(
        "--editable", "-e",
        action="store_true",
        help="Install package in editable mode (for development)"
    )
    
    args = parser.parse_args()
    
    print("🚀 Orama Python Client Installation")
    print("=" * 40)
    
    success = True
    
    if args.mode == "basic":
        success &= run_pip_install("requirements.txt")
        
    elif args.mode == "dev":
        success &= run_pip_install("requirements.txt")
        success &= run_pip_install("requirements-dev.txt")
        args.editable = True  # Always install in editable mode for dev
        
    elif args.mode == "prod":
        success &= run_pip_install("requirements-prod.txt")
        
    elif args.mode == "optional":
        success &= run_pip_install("requirements.txt")
        success &= run_pip_install("requirements-optional.txt")
        
    elif args.mode == "all":
        success &= run_pip_install("requirements.txt")
        success &= run_pip_install("requirements-dev.txt") 
        success &= run_pip_install("requirements-optional.txt")
        args.editable = True
    
    # Install package in editable mode if requested or for dev mode
    if args.editable and success:
        success &= install_package_editable()
    
    if success:
        print(f"\n✅ Installation completed successfully!")
        print(f"   Mode: {args.mode}")
        if args.editable:
            print(f"   Package installed in editable mode")
        print(f"\n🎉 You can now use the Orama client:")
        print(f"   >>> from orama import CollectionManager")
        print(f"   >>> manager = CollectionManager({{'collection_id': 'your-id', 'api_key': 'your-key'}})")
    else:
        print(f"\n❌ Installation failed. Please check the error messages above.")
        sys.exit(1)

if __name__ == "__main__":
    main()