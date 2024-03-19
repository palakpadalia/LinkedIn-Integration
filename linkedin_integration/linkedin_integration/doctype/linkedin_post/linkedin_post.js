// Copyright (c) 2024, Palak Padalia and contributors
// For license information, please see license.txt

frappe.ui.form.on('Linkedin Post', {
	refresh: function (frm) {
		

		frm.add_custom_button(__("Post"), function () {
			if (parseInt(localStorage.getItem('LE'))) {
				frappe.confirm(
					"Do you want to Post On LinkedIn?",
					function () {
						frappe.call({
							method:
								"linkedin_integration.linkedin_integration.doctype.linkedin.linkedin.post",
							args: {
								text: frm.doc.text,
								title: frm.doc.title,
								media: frm.doc.media,
								video: frm.doc.video,
								docname: frm.doc.name
							},
						});	
					}
				);
			} else {
				frappe.throw("Please enable the settings of Linkedin")
			}
		});
		frm.add_custom_button(__("Delete"), function () {
			if (parseInt(localStorage.getItem('LE'))) {
				frappe.confirm(
					"Do you want to Post On LinkedIn?",
					function () {

						frappe.call({

							method:
								"linkedin_integration.linkedin_integration.doctype.linkedin.linkedin.delete",
							args: {
								post_id: frm.doc.post_id,

							},
						});	
					}
				);
			} else {
				frappe.throw("Please enable the settings of Linkedin")
			}
		});
	}
});
