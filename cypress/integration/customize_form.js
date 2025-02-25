context("Customize Form", () => {
	before(() => {
		cy.login();
		cy.visit("/app/customize-form");
	});
	it("Changing to naming rule should update autoid", () => {
		cy.fill_field("doc_type", "ToDo", "Link").blur();
		cy.wait(2000);
		cy.findByRole("tab", { name: "Details" }).click();
		cy.click_form_section("Naming");
		const naming_rule_default_autoid_map = {
			"Set by user": "prompt",
			"By fieldname": "field:",
			Expression: "format:",
			"Expression (old style)": "",
			Random: "hash",
			"By script": "",
		};
		Cypress._.forOwn(naming_rule_default_autoid_map, (value, naming_rule) => {
			cy.fill_field("naming_rule", naming_rule, "Select");
			cy.get_field("autoid", "Data").should("have.value", value);
		});
	});
});
