// Test-only caller of unchanged, Git-blob-pinned WAM subsidy source.
// Minimal type/parameter shims do NOT implement node consensus or a network.
#include <wam/consensus/subsidy.h>
#include <consensus/params.h>
#include <wam/wam-params.h>
#include <cstdint>
#include <iostream>
#include <stdexcept>

static void require(bool ok) { if (!ok) throw std::runtime_error("PINNED_SUBSIDY_CONTRACT_DENIED"); }
struct Row { int height; int64_t subsidy; int64_t treasury; };
static_assert(sizeof(void*)==8, "SOURCE_CONTRACT_REQUIRES_64BIT_NATIVE_BUILD");
int main() {
    try {
        const Consensus::Params production{200000}, regtest{150};
        const Row rows[]={{0,200000000000000LL,0},{1,5000000000LL,250000000},
          {200000,5000000000LL,250000000},{200001,2500000000LL,125000000},
          {399999,2500000000LL,125000000},{400000,2500000000LL,125000000},
          {400001,1250000000LL,0},{600000,1250000000LL,0},{600001,625000000,0}};
        std::cout << "{\"source_contract_only\":true,\"core_binary_e2e\":false,\"production_parameter_vectors\":[";
        bool first=true;
        for (const Row& r: rows) {
            const auto sub=wam::GetBlockSubsidy(r.height,production);
            require(sub==r.subsidy);
            require(wam::GetDevFeeAmount(sub,r.height)==r.treasury);
            require(wam::GetMinerSubsidy(sub,r.height)==sub-r.treasury);
            if (!first) std::cout << ','; first=false;
            std::cout << "{\"height\":" << r.height << ",\"subsidy_atoms\":" << sub
              << ",\"treasury_atoms\":" << r.treasury << ",\"miner_atoms\":" << sub-r.treasury << '}';
        }
        const Row short_rows[]={{1,5000000000LL,250000000},{150,5000000000LL,250000000},
          {151,2500000000LL,125000000},{300,2500000000LL,125000000},
          {301,1250000000LL,62500000},{451,625000000,31250000},{4950,1,0},{4951,0,0}};
        for (const Row& r: short_rows) {
            require(wam::GetBlockSubsidy(r.height,regtest)==r.subsidy);
            require(wam::GetDevFeeAmount(r.subsidy,r.height)==r.treasury);
        }
        // Treasury cutoff must not depend on the subsidy/epoch. Cross the
        // height boundary while holding each nonzero amount constant.
        const int64_t nonzero[]={5000000000LL,2500000000LL,1250000000LL,625000000,1};
        for (const auto amount: nonzero) {
            require(wam::GetDevFeeAmount(amount,400000)==amount*5/100);
            require(wam::GetDevFeeAmount(amount,400001)==0);
            require(wam::GetDevFeeAmount(amount,600001)==0);
        }
        require(wam::GetLifetimeDevFee(production)==75000000000000LL);
        require(wam::GetLifetimeDevFee(regtest)==74999998050LL);
        require(wam::GetBlockSubsidy(-1,production)==0);
        require(wam::WAM_COINBASE_MATURITY==100);
        std::cout << "],\"treasury_cutoff_independent\":true,\"genesis_not_normal_reward\":true,"
          "\"production_parameter_lifetime_treasury_atoms\":75000000000000,"
          "\"regtest_lifetime_treasury_atoms\":74999998050,\"regtest_interval\":150,"
          "\"no_mainnet_node_or_network\":true}\n";
        return 0;
    } catch (...) { std::cerr << "PINNED_SUBSIDY_SOURCE_CONTRACT_DENIED\n"; return 2; }
}
