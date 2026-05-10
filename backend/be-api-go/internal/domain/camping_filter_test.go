package domain

import "testing"

func TestIsCampingFacility(t *testing.T) {
	cases := []struct {
		name string
		camp *Camp
		want bool
	}{
		{"nil", nil, false},
		{"empty", &Camp{}, false},
		{"camfit autoCamping", &Camp{Types: []string{"autoCamping"}}, true},
		{"camfit pension only", &Camp{Types: []string{"pension"}}, false},
		{"camfit bungalow only", &Camp{Types: []string{"bungalow"}}, false},
		{"camfit pension+autoCamping kept", &Camp{Types: []string{"pension", "autoCamping"}}, true},
		{"txcp 오토캠핑", &Camp{Types: []string{"오토캠핑"}}, true},
		{"txcp 펜션 only", &Camp{Types: []string{"펜션"}}, false},
		{"txcp BB008 unknown only", &Camp{Types: []string{"BB008"}}, false},
		{"txcp BB001 known camping", &Camp{Types: []string{"BB001"}}, true},
		{"txcp 오토캠핑 + BB999 kept", &Camp{Types: []string{"오토캠핑", "BB999"}}, true},
		{"camfit glamping", &Camp{Types: []string{"glamping"}}, true},
		{"camfit caravan", &Camp{Types: []string{"caravan"}}, true},
		{"camfit carCamping", &Camp{Types: []string{"carCamping"}}, true},
		{"camfit trailer", &Camp{Types: []string{"trailer"}}, true},
		{"camfit experience", &Camp{Types: []string{"experience"}}, true},
		{"location_types only camping", &Camp{LocationTypes: []string{"오토캠핑"}}, true},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			got := IsCampingFacility(tc.camp)
			if got != tc.want {
				t.Fatalf("IsCampingFacility(%+v) = %v, want %v", tc.camp, got, tc.want)
			}
		})
	}
}
