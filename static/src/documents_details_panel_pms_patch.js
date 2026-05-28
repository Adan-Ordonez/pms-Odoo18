/** @odoo-module **/
import { DocumentsDetailsPanel } from "@documents/components/documents_details_panel/documents_details_panel";
import { DateTimeField } from "@web/views/fields/datetime/datetime_field";
import { FloatField } from "@web/views/fields/float/float_field";

DocumentsDetailsPanel.components = {
    ...DocumentsDetailsPanel.components,
    DateTimeField,
    DateField: DateTimeField,
    FloatField,
};
