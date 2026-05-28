# -*- coding: utf-8 -*-
"""
Script to find and fix the 'amount_paid' field issue in sale.order views.
Run this script from Odoo shell:
    python odoo-bin shell -d YOUR_DATABASE_NAME < addons/pms/scripts/fix_amount_paid_view.py

Or execute it manually in the Odoo shell.
"""

import logging
_logger = logging.getLogger(__name__)

def fix_amount_paid_issue(env):
    """
    Find and report/fix views that reference 'amount_paid' in sale.order model.
    """
    print("\n" + "="*60)
    print("SEARCHING FOR 'amount_paid' REFERENCES IN sale.order VIEWS")
    print("="*60 + "\n")
    
    # 1. Search for views with amount_paid in sale.order
    views = env['ir.ui.view'].sudo().search([
        ('model', '=', 'sale.order'),
    ])
    
    problematic_views = []
    for view in views:
        arch = view.arch_db or view.arch or ''
        if 'amount_paid' in arch:
            problematic_views.append(view)
            print(f"FOUND PROBLEMATIC VIEW:")
            print(f"  ID: {view.id}")
            print(f"  Name: {view.name}")
            print(f"  Type: {view.type}")
            print(f"  Inherit ID: {view.inherit_id.name if view.inherit_id else 'None'}")
            print(f"  Active: {view.active}")
            print("-" * 40)
    
    if not problematic_views:
        print("No views found with 'amount_paid' in sale.order model.\n")
    else:
        print(f"\nTotal problematic views found: {len(problematic_views)}")
        print("\nTo fix, you can:")
        print("1. Delete these views using: view.unlink()")
        print("2. Or edit them to remove 'amount_paid' reference")
    
    # 2. Check for custom fields
    print("\n" + "="*60)
    print("CHECKING FOR CUSTOM 'amount_paid' FIELD IN sale.order")
    print("="*60 + "\n")
    
    fields = env['ir.model.fields'].sudo().search([
        ('model', '=', 'sale.order'),
        ('name', '=', 'amount_paid'),
    ])
    
    if fields:
        for field in fields:
            print(f"FOUND CUSTOM FIELD:")
            print(f"  ID: {field.id}")
            print(f"  Name: {field.name}")
            print(f"  Field Description: {field.field_description}")
            print(f"  Type: {field.ttype}")
            print(f"  State: {field.state}")
            print("-" * 40)
    else:
        print("No custom 'amount_paid' field found in sale.order model.\n")
    
    # 3. Check Studio customizations
    print("\n" + "="*60)
    print("CHECKING FOR STUDIO CUSTOMIZATIONS")
    print("="*60 + "\n")
    
    studio_views = env['ir.ui.view'].sudo().search([
        ('model', '=', 'sale.order'),
        ('name', 'ilike', 'studio'),
    ])
    
    if studio_views:
        for view in studio_views:
            print(f"FOUND STUDIO VIEW:")
            print(f"  ID: {view.id}")
            print(f"  Name: {view.name}")
            arch = view.arch_db or view.arch or ''
            if 'amount_paid' in arch:
                print(f"  *** CONTAINS 'amount_paid' ***")
            print("-" * 40)
    else:
        print("No Studio views found for sale.order.\n")
    
    print("\n" + "="*60)
    print("DIAGNOSIS COMPLETE")
    print("="*60 + "\n")
    
    return problematic_views


def delete_problematic_views(env, views):
    """Delete the problematic views."""
    for view in views:
        print(f"Deleting view: {view.id} - {view.name}")
        try:
            view.unlink()
            print(f"  Successfully deleted!")
        except Exception as e:
            print(f"  Error deleting: {e}")
            # Try to deactivate instead
            try:
                view.active = False
                print(f"  Deactivated instead.")
            except Exception as e2:
                print(f"  Could not deactivate: {e2}")


# Run the diagnosis
if 'env' in dir():
    problematic = fix_amount_paid_issue(env)
    
    if problematic:
        print("\nTo delete these views, run:")
        print("delete_problematic_views(env, problematic)")
        print("\nOr manually delete from Odoo interface:")
        print("Settings > Technical > User Interface > Views")
        for v in problematic:
            print(f"  - Search for ID: {v.id}")

































